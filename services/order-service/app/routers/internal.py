from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus, OrderStatusHistory
from app.estimate import lock_station
from app.routers.orders import ORDERS_CREATED, get_order_or_404, refresh_kitchen
from app.schemas import InternalOrderOut, PaymentConfirmIn
from app.security import verify_internal_key
from app.state_machine import change_status

router = APIRouter(
    prefix="/internal/orders",
    tags=["internal"],
    dependencies=[Depends(verify_internal_key)],
)


@router.get("/{order_id}", response_model=InternalOrderOut)
def internal_get_order(order_id: int, db: Session = Depends(get_db)):
    """payment-service gọi để lấy số tiền cần thanh toán."""
    return get_order_or_404(db, order_id)


@router.post("/{order_id}/payment-confirmed", response_model=InternalOrderOut)
def payment_confirmed(
    order_id: int, payload: PaymentConfirmIn, db: Session = Depends(get_db)
):
    """payment-service báo khách đã trả tiền ở trạm 1 (tiền mặt hoặc ZaloPay): đơn vào bếp.

    Gọi lại nhiều lần vẫn an toàn (idempotent).
    """
    order = get_order_or_404(db, order_id)
    lock_station(db, order.station_id)          # nhiều đơn vào bếp cùng lúc: xếp lần lượt
    order = get_order_or_404(db, order_id, lock=True)

    method = payload.method or order.payment_method or "ZALOPAY"
    paid_with = "tiền mặt" if method == "CASH" else "ZaloPay"

    if order.status in (OrderStatus.AWAITING_PAYMENT.value, OrderStatus.PENDING_PAYMENT.value):
        if order.payment_method != method:
            # Nhân viên vừa đổi sang tiền mặt nhưng khách đã kịp trả ZaloPay: ghi đúng cách
            # trả thật sự để quầy không thu tiền lần nữa
            order.payment_method = method
        note = f"Đã thanh toán {paid_with}, đơn vào bếp"
        if payload.transaction_ref and method == "ZALOPAY":
            note += f" (mã GD: {payload.transaction_ref})"
        change_status(order, OrderStatus.CONFIRMED, None, note)
        order.confirmed_at = datetime.now(timezone.utc)
        refresh_kitchen(db, order.station_id)   # xếp đơn vào hàng đợi bếp, tính giờ xong
        ORDERS_CREATED.labels(payment_method=method).inc()
        db.commit()
        db.refresh(order)
    elif order.status == OrderStatus.CANCELLED.value:
        # Đơn đã bị hủy mà tiền vẫn về: báo lỗi để payment-service ghi chú hoàn tiền
        raise HTTPException(status_code=409, detail="Đơn đã bị hủy")
    elif order.status == OrderStatus.HOLD.value:
        raise HTTPException(status_code=409, detail="Đơn chưa được trạm 1 nhận, chưa thu tiền")
    elif payload.method and order.payment_method != payload.method:
        order.payment_method = payload.method
        order.history.append(
            OrderStatusHistory(
                from_status=order.status,
                to_status=order.status,
                changed_by=None,
                note=f"Khách đã thanh toán {paid_with}, không cần thu tiền lần nữa",
            )
        )
        db.commit()
        db.refresh(order)
    # Các trạng thái khác: đã vào bếp rồi, không làm gì, trả 200

    return order
