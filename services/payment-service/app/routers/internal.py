from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Payment
from app.processing import sync_zalopay
from app.security import verify_internal_key

router = APIRouter(
    prefix="/internal/payments",
    tags=["internal"],
    dependencies=[Depends(verify_internal_key)],
)


# ---------- order-service hỏi đơn đã được thanh toán chưa ----------
@router.get("/order/{order_id}/paid")
def order_paid(order_id: int, sync: bool = False, db: Session = Depends(get_db)):
    """sync=true: hỏi ZaloPay các giao dịch còn PENDING trước khi trả lời.

    Dùng khi khách hủy đơn / đổi sang trả tại quầy: khách có thể vừa quét mã xong mà
    callback chưa tới. order-service phải gọi TRƯỚC khi khóa đơn, vì tra cứu thấy đã trả
    thì payment-service sẽ gọi ngược order-service để xác nhận đơn.
    """
    if sync and not config.MOCK_MODE:
        pending = db.scalars(
            select(Payment).where(
                Payment.order_id == order_id,
                Payment.method == "ZALOPAY",
                Payment.status == "PENDING",
            )
        ).all()
        for p in pending:
            sync_zalopay(db, p)

    paid = db.scalar(
        select(Payment).where(Payment.order_id == order_id, Payment.status == "SUCCESS")
    )
    return {"paid": paid is not None, "method": paid.method if paid else None}
