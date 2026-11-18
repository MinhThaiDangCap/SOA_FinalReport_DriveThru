import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, momo
from app.database import get_db
from app.models import Payment
from app.processing import PAYMENTS
from app.security import verify_internal_key

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/internal/payments",
    tags=["internal"],
    dependencies=[Depends(verify_internal_key)],
)


# ---------- order-service hỏi đơn đã được thanh toán chưa ----------
@router.get("/order/{order_id}/paid")
def order_paid(order_id: int, db: Session = Depends(get_db)):
    paid = db.scalar(
        select(Payment).where(Payment.order_id == order_id, Payment.status == "SUCCESS")
    )
    return {"paid": paid is not None, "method": paid.method if paid else None}


# ---------- order-service gọi khi khách hủy đơn đã trả tiền qua MoMo ----------
@router.post("/order/{order_id}/refund")
def refund_order(order_id: int, db: Session = Depends(get_db)):
    """Hoàn tiền giao dịch MoMo thành công của đơn. Gọi lại nhiều lần vẫn an toàn.

    Trả {"refunded": bool, "amount": int}. refunded=False nghĩa là đơn chưa có tiền để hoàn.
    MoMo từ chối/không phản hồi -> 502, order-service sẽ không hủy đơn.
    """
    payments = db.scalars(
        select(Payment)
        .where(Payment.order_id == order_id, Payment.method == "MOMO")
        .with_for_update()
    ).all()

    paid = next((p for p in payments if p.status == "SUCCESS"), None)
    if paid is None:
        refunded = next((p for p in payments if p.status == "REFUNDED"), None)
        if refunded:
            return {"refunded": True, "amount": refunded.amount}
        return {"refunded": False, "amount": 0}

    # Giao dịch giả lập (PAYMENT_MOCK_MODE) thì không có gì để gọi MoMo
    is_mock = config.MOCK_MODE or str(paid.transaction_no or "").startswith("MOCK")
    if is_mock:
        refund_trans = f"MOCKRF{paid.id}"
    else:
        if not paid.transaction_no:
            raise HTTPException(status_code=502, detail="Thiếu mã giao dịch MoMo để hoàn tiền")
        refund_ref = f"RF{order_id}P{paid.id}-{uuid.uuid4().hex[:10]}"
        try:
            refund_trans = momo.refund(
                refund_ref, paid.amount, paid.transaction_no, f"Hoan tien don hang {order_id}"
            )
        except momo.MomoError as e:
            db.rollback()
            logger.error("Hoàn tiền đơn %s thất bại: %s", order_id, e)
            raise HTTPException(status_code=502, detail="MoMo chưa hoàn được tiền")

    paid.status = "REFUNDED"
    paid.note = f"Đã hoàn tiền MoMo khi khách hủy đơn (mã hoàn {refund_trans})"[:200]
    db.commit()
    PAYMENTS.labels("MOMO", "refunded").inc()
    return {"refunded": True, "amount": paid.amount}
