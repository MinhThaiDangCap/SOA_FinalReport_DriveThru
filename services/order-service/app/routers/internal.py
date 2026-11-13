from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus
from app.routers.orders import get_order_or_404
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
    """payment-service báo đã thu tiền. Gọi lại nhiều lần vẫn an toàn (idempotent)."""
    order = get_order_or_404(db, order_id, lock=True)

    if order.status == OrderStatus.PENDING_PAYMENT.value:
        note = "Thanh toán VNPay thành công"
        if payload.transaction_ref:
            note += f" (mã GD: {payload.transaction_ref})"
        change_status(order, OrderStatus.CONFIRMED, None, note)
        db.commit()
        db.refresh(order)
    elif order.status == OrderStatus.CANCELLED.value:
        # Khách đã hủy rồi mà tiền vẫn về: báo lỗi để payment-service xử lý hoàn tiền
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="Đơn đã bị hủy")
    # Các trạng thái khác: đã CONFIRMED hoặc xa hơn, không làm gì, trả 200

    return order