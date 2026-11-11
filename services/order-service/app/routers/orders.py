from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter
from sqlalchemy.orm import Session

from app.coupons import apply_coupon
from app.database import get_db
from app.menu_client import get_menu_items
from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.schemas import OrderCreate, OrderOut
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/orders", tags=["orders"])

ORDERS_CREATED = Counter(
    "orders_created_total", "Số đơn hàng đã tạo", ["payment_method"]
)


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


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    # Khách chỉ xem được đơn của mình; nhân viên/admin xem được tất cả
    if user["role"] == "CUSTOMER" and order.customer_id != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    return order