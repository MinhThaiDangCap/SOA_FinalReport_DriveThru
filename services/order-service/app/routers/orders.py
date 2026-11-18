from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from prometheus_client import Counter
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import payment_client
from app.coupons import apply_coupon
from app.database import get_db
from app.menu_client import get_menu_items
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.schemas import OrderCreate, OrderOut, StationOrderStats, StatusUpdate
from app.security import get_current_user, require_roles
from app.state_machine import ALLOWED, change_status

router = APIRouter(prefix="/api/orders", tags=["orders"])

ORDERS_CREATED = Counter(
    "orders_created_total", "Số đơn hàng đã tạo", ["payment_method"]
)

# Các trạng thái nhân viên cần nhìn thấy trong hàng đợi
QUEUE_STATUSES = [
    OrderStatus.CONFIRMED.value,
    OrderStatus.PREPARING.value,
    OrderStatus.READY.value,
    OrderStatus.ARRIVED.value,
]


# ---------- Hàm dùng chung ----------
def get_order_or_404(db: Session, order_id: int, lock: bool = False) -> Order:
    """lock=True khóa dòng đơn hàng (FOR UPDATE) để 2 request không đổi trạng thái cùng lúc."""
    stmt = select(Order).where(Order.id == order_id)
    if lock:
        stmt = stmt.with_for_update()
    order = db.scalar(stmt)
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return order


def ensure_staff_station(user: dict, order: Order) -> None:
    """Nhân viên chỉ thao tác được đơn của cửa hàng mình; admin thì mọi cửa hàng."""
    if user["role"] == "STAFF" and user["station_id"] != order.station_id:
        raise HTTPException(status_code=403, detail="Đơn này thuộc cửa hàng khác")


# ---------- Khách: tạo đơn ----------
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

    order_items: list[OrderItem] = []
    subtotal = 0
    for item_id, qty in qty_by_item.items():
        m = menu.get(item_id)
        if m is None:
            raise HTTPException(
                status_code=400,
                detail=f"Món {item_id} không tồn tại ở cửa hàng này",
            )
        if not m.get("available", True):
            raise HTTPException(
                status_code=400, detail=f"Món '{m['name']}' hiện đã hết"
            )
        subtotal += m["price"] * qty
        order_items.append(
            OrderItem(
                menu_item_id=item_id,
                item_name=m["name"],
                unit_price=m["price"],
                quantity=qty,
            )
        )

    # 3. Mã giảm giá
    discount, coupon_code = apply_coupon(db, payload.coupon_code, subtotal)

    # 4. Trả tại quầy vào thẳng CONFIRMED, MoMo phải chờ thanh toán
    if payload.payment_method == "CASH":
        status = OrderStatus.CONFIRMED.value
        note = "Khách chọn trả tại quầy"
    else:
        status = OrderStatus.PENDING_PAYMENT.value
        note = "Chờ thanh toán MoMo"

    order = Order(
        customer_id=user["id"],
        station_id=payload.station_id,
        license_plate=payload.license_plate,
        status=status,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        discount_amount=discount,
        total_amount=subtotal - discount,
        coupon_code=coupon_code,
    )
    order.items = order_items
    order.history.append(
        OrderStatusHistory(
            from_status=None, to_status=status, changed_by=user["id"], note=note
        )
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    ORDERS_CREATED.labels(payment_method=payload.payment_method).inc()
    return order


# ---------- Khách: xem đơn của mình ----------
@router.get("/me", response_model=list[OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    stmt = (
        select(Order)
        .where(Order.customer_id == user["id"])
        .order_by(Order.id.desc())
    )
    return db.scalars(stmt).all()


# ---------- Nhân viên / admin: hàng đợi ----------
@router.get("/queue", response_model=list[OrderOut])
def station_queue(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    if user["role"] == "STAFF":
        station_id = user["station_id"]
        if station_id is None:
            raise HTTPException(
                status_code=400, detail="Tài khoản nhân viên chưa được gán cửa hàng"
            )

    stmt = select(Order).where(Order.status.in_(QUEUE_STATUSES))
    if station_id is not None:
        stmt = stmt.where(Order.station_id == station_id)
    stmt = stmt.order_by(Order.id.asc())  # đơn cũ nhất lên đầu
    return db.scalars(stmt).all()


# ---------- Nhân viên / admin: đơn đã xong gần đây ----------
@router.get("/recent", response_model=list[OrderOut])
def recent_orders(
    station_id: int | None = Query(default=None, description="Chỉ admin dùng"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    if user["role"] == "STAFF":
        station_id = user["station_id"]
    done = (OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value)
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

    S = OrderStatus
    completed = Order.status == S.COMPLETED.value
    is_today = Order.created_at >= today_start
    active = Order.status.in_(QUEUE_STATUSES)

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
    # Khách chỉ xem được đơn của mình; nhân viên chỉ xem đơn cửa hàng mình
    if user["role"] == "CUSTOMER" and order.customer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    ensure_staff_station(user, order)
    return order


# ---------- Nhân viên / admin: cập nhật trạng thái ----------
@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    order = get_order_or_404(db, order_id, lock=True)
    ensure_staff_station(user, order)

    # Đơn trả tại quầy: phải ghi nhận đã thu tiền (payment-service) rồi mới được hoàn thành
    # (chỉ hỏi khi bước chuyển hợp lệ, để lỗi sai trạng thái vẫn trả 409 như cũ)
    if (
        payload.status == OrderStatus.COMPLETED.value
        and OrderStatus.COMPLETED in ALLOWED[OrderStatus(order.status)]
        and order.payment_method == "CASH"
        and not payment_client.is_paid(order.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="Đơn trả tại quầy chưa được xác nhận thu tiền, không thể hoàn thành",
        )

    change_status(order, OrderStatus(payload.status), user["id"], payload.note)
    db.commit()
    db.refresh(order)
    return order


# ---------- Khách: hủy đơn ----------
@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    order = get_order_or_404(db, order_id, lock=True)
    if order.customer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")

    cancellable = (OrderStatus.PENDING_PAYMENT.value, OrderStatus.CONFIRMED.value)
    if order.status not in cancellable:
        raise HTTPException(
            status_code=409,
            detail=f"Không thể hủy đơn đang ở trạng thái {order.status}",
        )

    note = "Khách hủy đơn"
    # Đơn MoMo đã CONFIRMED tức là đã trả tiền: hoàn tiền trước, thành công mới hủy
    if order.payment_method == "MOMO" and order.status == OrderStatus.CONFIRMED.value:
        result = payment_client.refund_order(order.id)
        if result.get("refunded"):
            amount = f"{result.get('amount', 0):,}".replace(",", ".")
            note = f"Khách hủy đơn, đã hoàn {amount}đ về ví MoMo"

    change_status(order, OrderStatus.CANCELLED, user["id"], note)
    db.commit()
    db.refresh(order)
    return order


# ---------- Khách: báo "Tôi đã đến" ----------
@router.post("/{order_id}/arrived", response_model=OrderOut)
def customer_arrived(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    order = get_order_or_404(db, order_id, lock=True)
    if order.customer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")

    change_status(order, OrderStatus.ARRIVED, user["id"], "Khách báo đã đến")
    db.commit()
    db.refresh(order)
    return order