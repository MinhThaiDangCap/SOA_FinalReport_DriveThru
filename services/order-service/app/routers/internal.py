from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus, OrderStatusHistory
from app.routers.orders import get_order_or_404, update_estimate
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
        note = "Thanh toán MoMo thành công"
        if payload.transaction_ref:
            note += f" (mã GD: {payload.transaction_ref})"
        change_status(order, OrderStatus.CONFIRMED, None, note)
        update_estimate(db, order)  # đã trả tiền: đơn vào hàng đợi của bếp
        db.commit()
        db.refresh(order)
    elif order.status == OrderStatus.CANCELLED.value:
        # Khách đã hủy rồi mà tiền vẫn về: báo lỗi để payment-service xử lý hoàn tiền
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="Đơn đã bị hủy")
    elif order.payment_method == "CASH":
        # Khách đã mở trang MoMo rồi mới đổi sang trả tại quầy, sau đó vẫn trả MoMo xong:
        # tiền đã vào, ghi lại là MoMo để quầy không thu tiền mặt lần nữa
        order.payment_method = "MOMO"
        order.history.append(
            OrderStatusHistory(
                from_status=order.status,
                to_status=order.status,
                changed_by=None,
                note="Khách đã thanh toán MoMo, không cần thu tiền mặt",
            )
        )
        db.commit()
        db.refresh(order)
    # Các trạng thái khác: đã CONFIRMED hoặc xa hơn, không làm gì, trả 200

    return order