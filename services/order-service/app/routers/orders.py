from fastapi import APIRouter, Depends, HTTPException, Query
from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coupons import apply_coupon
from app.database import get_db
from app.menu_client import get_menu_items
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.schemas import OrderCreate, OrderOut, StatusUpdate
from app.security import get_current_user, require_roles
from app.state_machine import change_status

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

    # 4. Trả tại quầy vào thẳng CONFIRMED, VNPay phải chờ thanh toán
    if payload.payment_method == "CASH":
        status = OrderStatus.CONFIRMED.value
        note = "Khách chọn trả tại quầy"
    else:
        status = OrderStatus.PENDING_PAYMENT.value
        note = "Chờ thanh toán VNPay"

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

    change_status(order, OrderStatus.CANCELLED, user["id"], "Khách hủy đơn")
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