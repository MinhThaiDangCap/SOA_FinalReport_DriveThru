"""API đơn hàng theo mô hình 2 trạm.

Khách đặt trước trên web (chưa trả tiền) -> nhận mã 4 số, đơn ĐANG TREO.
Trạm 1: khách đọc mã, nhân viên đối chiếu biển số, khách trả tiền mặt / ZaloPay -> đơn vào bếp.
Bếp: làm theo hàng đợi ưu tiên (app/estimate.py), in phiếu dán lên túi, bấm "Món đã xong".
Trạm 2: khách đọc mã, nhân viên đối chiếu biển số, giao món.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from prometheus_client import Counter
from sqlalchemy import case, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import payment_client
from app.coupons import apply_coupon
from app.database import get_db
from app.estimate import (
    DEFAULT_KITCHEN_CAPACITY,
    KITCHEN_STATUSES,
    TYPICAL_ORDER_MINUTES,
    lock_station,
    order_prep_minutes,
    recompute_station,
    start_preparing,
    wait_minutes_for_new_order,
)
from app.menu_client import get_kitchen_capacities, get_menu_items
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.pickup import new_pickup_code, normalize_plate, vn_today
from app.schemas import (
    CheckIn,
    OrderCreate,
    OrderOut,
    PlateUpdate,
    StationOrderStats,
    StationWaitTime,
    StatusUpdate,
)
from app.security import get_current_user, require_roles
from app.state_machine import change_status

router = APIRouter(prefix="/api/orders", tags=["orders"])

# Giữ tên metric cũ để dashboard Grafana không đổi: đếm đơn đã trả tiền ở trạm 1 và vào bếp,
# chia theo cách trả (đơn treo chưa trả tiền chưa được đếm)
ORDERS_CREATED = Counter(
    "orders_created_total", "Số đơn đã trả tiền ở trạm 1 và vào bếp", ["payment_method"]
)

S = OrderStatus
HOLD_GRACE_MINUTES = 10  # giữ đơn thêm 10 phút sau giờ khách hẹn tới

# Đơn còn đang xử lý (chưa hoàn thành / hủy)
ACTIVE_STATUSES = [
    S.HOLD.value,
    S.AWAITING_PAYMENT.value,
    S.CONFIRMED.value,
    S.PREPARING.value,
    S.READY.value,
    S.PENDING_PAYMENT.value,
    S.ARRIVED.value,
]
# Đơn chưa trả tiền: hủy được, không phát sinh hoàn tiền
UNPAID_STATUSES = (S.HOLD.value, S.AWAITING_PAYMENT.value, S.PENDING_PAYMENT.value)
# Vai trò gắn với một chi nhánh: chỉ thao tác được đơn của chi nhánh mình
STATION_ROLES = ("STAFF", "KITCHEN")


# ---------- Hàm dùng chung ----------
def get_order_or_404(db: Session, order_id: int, lock: bool = False) -> Order:
    """lock=True khóa dòng đơn hàng (FOR UPDATE) để 2 request không đổi trạng thái cùng lúc."""
    stmt = select(Order).where(Order.id == order_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    order = db.scalar(stmt)
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order


def kitchen_capacity(station_id: int) -> int:
    return get_kitchen_capacities().get(station_id, DEFAULT_KITCHEN_CAPACITY)


def refresh_kitchen(db: Session, station_id: int) -> list[Order]:
    """Tính lại giờ dự kiến của cả hàng đợi bếp (gọi sau lock_station). Không commit."""
    db.flush()
    return recompute_station(db, station_id, kitchen_capacity(station_id))


def ensure_station(user: dict, order: Order) -> None:
    """Nhân viên trạm và bếp chỉ thao tác được đơn của chi nhánh mình; admin thì mọi nơi."""
    if user["role"] in STATION_ROLES and user["station_id"] != order.station_id:
        raise HTTPException(status_code=403, detail="Đơn này thuộc chi nhánh khác")


def station_of(user: dict, station_id: int | None) -> int | None:
    """Nhân viên/bếp luôn dùng chi nhánh trong token; admin chọn qua query (hoặc tất cả)."""
    if user["role"] in STATION_ROLES:
        if user["station_id"] is None:
            raise HTTPException(status_code=400, detail="Tài khoản chưa được gán chi nhánh")
        return user["station_id"]
    return station_id


def log_note(order: Order, user_id: int | None, note: str) -> None:
    """Ghi lịch sử không đổi trạng thái (sửa biển số, đổi cách trả...)."""
    order.history.append(
        OrderStatusHistory(
            from_status=order.status, to_status=order.status, changed_by=user_id, note=note
        )
    )


# ---------- Khách: đặt trước ----------
@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    # 1. Gộp các dòng trùng món
    qty_by_item: dict[int, int] = {}
    for it in payload.items:
        qty_by_item[it.menu_item_id] = qty_by_item.get(it.menu_item_id, 0) + it.quantity
    if any(q > 20 for q in qty_by_item.values()):
        raise HTTPException(status_code=400, detail="Mỗi món tối đa 20 phần")

    # 2. Hỏi menu-service để lấy tên và giá (không tin giá client gửi lên)
    menu = get_menu_items(payload.station_id, list(qty_by_item))

    lines: list[tuple[int, dict, int]] = []
    subtotal = 0
    for item_id, qty in qty_by_item.items():
        m = menu.get(item_id)
        if m is None:
            raise HTTPException(
                status_code=400, detail=f"Món {item_id} không tồn tại ở cửa hàng này"
            )
        if not m.get("available", True):
            raise HTTPException(status_code=400, detail=f"Món '{m['name']}' hiện đã hết")
        subtotal += m["price"] * qty
        lines.append((item_id, m, qty))

    # 3. Mã giảm giá
    discount, coupon_code = apply_coupon(db, payload.coupon_code, subtotal)

    # 4. Giờ hẹn tới trạm 1 và hạn giữ đơn
    now = datetime.now(timezone.utc)
    expected = now + timedelta(minutes=payload.arrival_minutes)
    expires = expected + timedelta(minutes=HOLD_GRACE_MINUTES)

    # 5. Lưu đơn kèm mã nhận món; hai đơn bốc trùng mã cùng lúc thì bốc lại
    for _ in range(5):
        day = vn_today()
        code = new_pickup_code(db, payload.station_id, day)
        if code is None:
            raise HTTPException(status_code=503, detail="Cửa hàng đã hết mã đơn trong ngày")
        items = [
            OrderItem(
                menu_item_id=item_id,
                item_name=m["name"],
                unit_price=m["price"],
                quantity=qty,
                prep_minutes=m.get("prep_minutes", 3),
            )
            for item_id, m, qty in lines
        ]
        order = Order(
            customer_id=user["id"],
            station_id=payload.station_id,
            license_plate=payload.license_plate,
            contact_phone=payload.contact_phone,
            status=S.HOLD.value,
            pickup_code=code,
            pickup_date=day,
            expected_arrival_at=expected,
            hold_expires_at=expires,
            subtotal=subtotal,
            discount_amount=discount,
            total_amount=subtotal - discount,
            coupon_code=coupon_code,
            prep_minutes=order_prep_minutes([(it.prep_minutes, it.quantity) for it in items]),
        )
        order.items = items
        order.history.append(
            OrderStatusHistory(
                from_status=None,
                to_status=S.HOLD.value,
                changed_by=user["id"],
                note=f"Đặt trước, mã {code}, hẹn tới trạm 1 trong {payload.arrival_minutes} phút",
            )
        )
        db.add(order)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise HTTPException(status_code=503, detail="Không tạo được mã đơn, vui lòng thử lại")

    db.refresh(order)
    return order


# ---------- Khách: xem đơn của mình ----------
@router.get("/me", response_model=list[OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    stmt = select(Order).where(Order.customer_id == user["id"]).order_by(Order.id.desc())
    return db.scalars(stmt).all()


# ---------- Trạm 1: đơn đang treo / đang chờ thanh toán ----------
@router.get("/station/holds", response_model=list[OrderOut])
def station_holds(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    """Đơn khách đã đặt nhưng chưa trả tiền ở trạm 1, khách hẹn tới sớm nhất lên đầu.

    Đơn quá hạn giữ có is_overdue=true (giao diện tô đỏ). Hệ thống không tự hủy:
    nhân viên xem số điện thoại và tự quyết định hủy.
    """
    station_id = station_of(user, station_id)
    stmt = select(Order).where(
        Order.status.in_((S.HOLD.value, S.AWAITING_PAYMENT.value))
    )
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    return db.scalars(stmt.order_by(Order.expected_arrival_at.asc(), Order.id.asc())).all()


# ---------- Trạm 1 / Trạm 2: tìm đơn theo mã hoặc biển số ----------
@router.get("/station/lookup", response_model=list[OrderOut])
def lookup_orders(
    q: str = Query(min_length=2, max_length=20, description="Mã 4 số hoặc biển số"),
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    station_id = station_of(user, station_id)
    plate = normalize_plate(q)
    plate_col = func.upper(
        func.replace(func.replace(func.replace(Order.license_plate, "-", ""), ".", ""), " ", "")
    )
    stmt = select(Order).where(
        Order.status.in_(ACTIVE_STATUSES),
        or_(Order.pickup_code == q.strip(), plate_col.contains(plate) if plate else false()),
    )
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    return db.scalars(stmt.order_by(Order.id.desc()).limit(20)).all()


# ---------- Trạm 1: nhận đơn, khách chọn cách trả ----------
@router.post("/{order_id}/check-in", response_model=OrderOut)
def check_in(
    order_id: int,
    payload: CheckIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    """Khách đã tới trạm 1, đọc mã, biển số khớp. Đơn chuyển sang chờ thanh toán.

    - Tiền mặt: nhân viên thu rồi bấm "Đã thu tiền" (payment-service), đơn vào bếp.
    - ZaloPay: trang đơn trên điện thoại khách hiện nút thanh toán; callback về thì
      đơn tự vào bếp.
    Gọi lại khi đơn đang chờ thanh toán để đổi cách trả.
    """
    order = get_order_or_404(db, order_id, lock=True)
    ensure_station(user, order)

    if order.status == S.HOLD.value:
        order.payment_method = payload.payment_method
        order.checked_in_at = datetime.now(timezone.utc)
        method = "tiền mặt" if payload.payment_method == "CASH" else "ZaloPay"
        change_status(order, S.AWAITING_PAYMENT, user["id"], f"Trạm 1 nhận đơn, khách trả {method}")
    elif order.status == S.AWAITING_PAYMENT.value:
        if order.payment_method != payload.payment_method:
            order.payment_method = payload.payment_method
            method = "tiền mặt" if payload.payment_method == "CASH" else "ZaloPay"
            log_note(order, user["id"], f"Đổi sang trả {method}")
    else:
        raise HTTPException(
            status_code=409,
            detail="Đơn không còn chờ xác nhận ở trạm 1 (đã thanh toán, hoàn thành hoặc đã hủy)",
        )
    db.commit()
    db.refresh(order)
    return order


# ---------- Khách (đơn đang treo) / Trạm 1: sửa biển số ----------
@router.patch("/{order_id}/plate", response_model=OrderOut)
def update_plate(
    order_id: int,
    payload: PlateUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER", "STAFF", "ADMIN")),
):
    """Khách gõ sai biển số hoặc đổi xe: khách tự sửa khi đơn còn treo; tại trạm 1 nhân viên
    sửa sau khi xác minh bằng tên / số điện thoại. Mọi lần sửa đều ghi lịch sử."""
    order = get_order_or_404(db, order_id, lock=True)
    if user["role"] == "CUSTOMER":
        if order.customer_id != user["id"]:
            raise HTTPException(status_code=403, detail="Không đủ quyền")
        allowed = (S.HOLD.value,)
    else:
        ensure_station(user, order)
        allowed = (S.HOLD.value, S.AWAITING_PAYMENT.value)
    if order.status not in allowed:
        raise HTTPException(status_code=409, detail="Không thể sửa biển số ở bước này")

    old = order.license_plate
    if payload.license_plate != old:
        order.license_plate = payload.license_plate
        log_note(order, user["id"], f"Sửa biển số {old} -> {payload.license_plate}")
        db.commit()
        db.refresh(order)
    return order


# ---------- Bếp: hàng đợi theo thứ tự ưu tiên ----------
@router.get("/kitchen", response_model=list[OrderOut])
def kitchen_queue(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng (bắt buộc)"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("KITCHEN", "ADMIN")),
):
    """Các đơn đã trả tiền, theo thứ tự bếp nên làm: đơn đang làm, đơn chờ quá lâu,
    rồi đơn làm nhanh trước. Giờ dự kiến được tính lại mỗi lần bếp tải hàng đợi."""
    station_id = station_of(user, station_id)
    if station_id is None:
        raise HTTPException(status_code=400, detail="Cần chọn chi nhánh (station_id)")
    lock_station(db, station_id)
    ordered = refresh_kitchen(db, station_id)
    db.commit()
    return ordered


# ---------- Trạm 2: đơn đã xong, mời khách ra nhận ----------
@router.get("/station/ready", response_model=list[OrderOut])
def ready_orders(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    station_id = station_of(user, station_id)
    stmt = select(Order).where(Order.status == S.READY.value)
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    return db.scalars(stmt.order_by(Order.updated_at.asc(), Order.id.asc())).all()


# ---------- Admin / nhân viên: tất cả đơn đang xử lý ----------
@router.get("/queue", response_model=list[OrderOut])
def station_queue(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "KITCHEN", "ADMIN")),
):
    station_id = station_of(user, station_id)
    stmt = select(Order).where(Order.status.in_(ACTIVE_STATUSES))
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    return db.scalars(stmt.order_by(Order.id.asc())).all()


# ---------- Công khai: độ đông của từng cửa hàng (trang chủ) ----------
@router.get("/wait-times", response_model=list[StationWaitTime])
def wait_times(db: Session = Depends(get_db)):
    """Không cần đăng nhập, chỉ trả số lượng, không lộ thông tin đơn.

    estimated_minutes = thời gian chờ tới lượt trong bếp + một đơn điển hình,
    tính từ lúc khách trả tiền ở trạm 1.
    """
    rows = db.execute(
        select(Order.station_id, func.count(Order.id))
        .where(Order.status.in_(KITCHEN_STATUSES))
        .group_by(Order.station_id)
    ).all()
    capacities = get_kitchen_capacities() if rows else {}
    return [
        StationWaitTime(
            station_id=station_id,
            queue_count=count,
            estimated_minutes=wait_minutes_for_new_order(
                db, station_id, capacities.get(station_id, DEFAULT_KITCHEN_CAPACITY)
            )
            + TYPICAL_ORDER_MINUTES,
        )
        for station_id, count in rows
    ]


# ---------- Nhân viên / bếp / admin: đơn đã xong gần đây ----------
@router.get("/recent", response_model=list[OrderOut])
def recent_orders(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "KITCHEN", "ADMIN")),
):
    station_id = station_of(user, station_id)
    done = (S.COMPLETED.value, S.CANCELLED.value)
    stmt = select(Order).where(Order.status.in_(done))
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    return db.scalars(stmt.order_by(Order.updated_at.desc(), Order.id.desc()).limit(limit)).all()


# ---------- Admin: thống kê theo cửa hàng ----------
@router.get("/stats", response_model=list[StationOrderStats])
def order_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    # "Hôm nay" tính theo giờ Việt Nam
    vn = timezone(timedelta(hours=7))
    today_start = datetime.now(vn).replace(hour=0, minute=0, second=0, microsecond=0)

    completed = Order.status == S.COMPLETED.value
    is_today = Order.created_at >= today_start
    active = Order.status.in_(ACTIVE_STATUSES)

    def count_if(cond):
        return func.sum(case((cond, 1), else_=0))

    rows = db.execute(
        select(
            Order.station_id,
            func.count(Order.id),
            count_if(active),
            count_if(completed),
            count_if(Order.status == S.CANCELLED.value),
            func.sum(case((completed, Order.total_amount), else_=0)),
            count_if(is_today),
            func.sum(case((completed & is_today, Order.total_amount), else_=0)),
        )
        .group_by(Order.station_id)
        .order_by(Order.station_id)
    ).all()

    return [
        StationOrderStats(
            station_id=r[0],
            total_orders=r[1],
            active_orders=r[2] or 0,
            completed_orders=r[3] or 0,
            cancelled_orders=r[4] or 0,
            revenue=r[5] or 0,
            today_orders=r[6] or 0,
            today_revenue=r[7] or 0,
        )
        for r in rows
    ]


# ---------- Xem chi tiết một đơn ----------
@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    order = get_order_or_404(db, order_id)
    # Khách chỉ xem được đơn của mình; nhân viên / bếp chỉ xem đơn chi nhánh mình
    if user["role"] == "CUSTOMER" and order.customer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    ensure_station(user, order)
    return order


# ---------- Bếp / Trạm 2: cập nhật trạng thái ----------
# Ai được chuyển đơn sang trạng thái nào
STATUS_ROLES = {
    S.PREPARING.value: ("KITCHEN", "ADMIN"),   # bếp bắt đầu làm
    S.READY.value: ("KITCHEN", "ADMIN"),       # bếp làm xong, đã dán phiếu lên túi
    S.COMPLETED.value: ("STAFF", "ADMIN"),     # trạm 2 đã giao cho khách
}


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "KITCHEN", "ADMIN")),
):
    if user["role"] not in STATUS_ROLES[payload.status]:
        who = "bếp" if user["role"] == "STAFF" else "nhân viên trạm 2"
        raise HTTPException(status_code=403, detail=f"Bước này do {who} thực hiện")

    order = get_order_or_404(db, order_id)
    ensure_station(user, order)
    lock_station(db, order.station_id)          # khóa hàng đợi bếp trước, rồi tới dòng đơn
    order = get_order_or_404(db, order_id, lock=True)

    change_status(order, OrderStatus(payload.status), user["id"], payload.note)
    if order.status == S.PREPARING.value:
        start_preparing(order)                  # xong sau đúng số phút của đơn
    if order.status in (S.PREPARING.value, S.READY.value):
        refresh_kitchen(db, order.station_id)   # bếp có thêm / bớt chỗ: tính lại các đơn khác
    db.commit()
    db.refresh(order)
    return order


# ---------- Khách / Trạm 1: hủy đơn chưa trả tiền ----------
@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER", "STAFF", "ADMIN")),
):
    """Chỉ hủy được đơn CHƯA trả tiền (đang treo hoặc đang chờ thanh toán ở trạm 1).

    Khách tự hủy đơn của mình. Nhân viên trạm 1 hủy đơn của chi nhánh, thường là đơn quá
    hạn giữ (đã có số điện thoại để tự gọi khách nếu muốn). Hệ thống không tự hủy đơn.
    Đã trả tiền thì đơn đã vào bếp, không hủy nữa, nên không bao giờ phải hoàn tiền.
    """
    order = get_order_or_404(db, order_id)
    if user["role"] == "CUSTOMER":
        if order.customer_id != user["id"]:
            raise HTTPException(status_code=403, detail="Không đủ quyền")
        note = "Khách hủy đơn"
    else:
        ensure_station(user, order)
        note = "Nhân viên trạm 1 hủy đơn" + (" quá hạn giữ" if order.is_overdue else "")

    # Đơn đang trả ZaloPay: khách có thể vừa trả xong mà callback chưa tới. Hỏi
    # payment-service (tự tra cứu ZaloPay) TRƯỚC khi khóa đơn: nếu đã trả thì payment-service
    # gọi lại order-service xác nhận đơn, đơn vào bếp và không hủy được nữa.
    if order.payment_method == "ZALOPAY" and order.status in (
        S.AWAITING_PAYMENT.value,
        S.PENDING_PAYMENT.value,
    ):
        payment_client.is_paid(order.id, sync=True)
        db.expire_all()

    order = get_order_or_404(db, order_id, lock=True)
    if order.status not in UNPAID_STATUSES:
        reasons = {
            S.COMPLETED.value: "Đơn đã hoàn thành nên không thể hủy.",
            S.CANCELLED.value: "Đơn này đã được hủy trước đó.",
        }
        raise HTTPException(
            status_code=409,
            detail=reasons.get(
                order.status, "Đơn đã thanh toán và đang được bếp làm nên không thể hủy."
            ),
        )

    change_status(order, S.CANCELLED, user["id"], note)
    db.commit()
    db.refresh(order)
    return order
