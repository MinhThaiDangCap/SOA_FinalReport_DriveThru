import json
from datetime import datetime, timezone

from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import momo, order_client
from app.models import Payment, PaymentCallback

PAYMENTS = Counter(
    "payments_total", "Số giao dịch thanh toán", ["method", "result"]
)


def process_momo_result(
    db: Session, params: dict, skip_signature: bool = False
) -> str:
    """Xử lý kết quả MoMo gửi về (IPN hoặc redirect). Gọi lại nhiều lần vẫn an toàn.

    Trả về: ok | pending | already_processed | invalid_signature | not_found
            | invalid_amount | retry (lỗi tạm thời, MoMo nên gửi lại)
    """
    txn_ref = str(params.get("orderId", ""))
    valid = True if skip_signature else momo.verify(params)
    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))

    # Luôn lưu lại callback (kể cả sai chữ ký) để đối soát
    db.add(
        PaymentCallback(
            payment_id=payment.id if payment else None,
            txn_ref=txn_ref[:60],
            raw_params=json.dumps(params, ensure_ascii=False),
            signature_valid=valid,
            response_code=str(params.get("resultCode", ""))[:5] or None,
        )
    )
    db.commit()

    # 1. Chữ ký
    if not valid:
        return "invalid_signature"
    # 2. Giao dịch tồn tại
    if payment is None:
        return "not_found"
    # 3. Số tiền khớp
    try:
        paid_amount = int(params.get("amount", ""))
        result_code = int(params.get("resultCode", ""))
    except (TypeError, ValueError):
        return "invalid_amount"
    if paid_amount != payment.amount:
        return "invalid_amount"
    # 4. MoMo còn đang xử lý: chưa kết luận, chờ lần gọi sau
    if result_code in momo.PENDING_CODES:
        return "pending"

    # 5. Khóa dòng để hai callback đến cùng lúc không xử lý trùng
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment.status != "PENDING":
        return "already_processed"

    if result_code == momo.SUCCESS_CODE:
        ref = str(params.get("transId") or "") or None
        try:
            code, _ = order_client.mark_paid(payment.order_id, ref)
        except order_client.OrderServiceUnavailable:
            db.rollback()
            return "retry"

        if code == 409:
            payment.note = "Đơn đã bị hủy trước khi thanh toán, cần hoàn tiền"
        elif code != 200:
            db.rollback()
            return "retry"

        payment.status = "SUCCESS"
        payment.paid_at = datetime.now(timezone.utc)
        payment.transaction_no = ref
        payment.bank_code = str(params.get("payType") or "")[:20] or None
        PAYMENTS.labels("MOMO", "success").inc()
    else:
        payment.status = "FAILED"
        payment.note = f"MoMo mã lỗi {result_code}: {params.get('message') or ''}"[:200]
        PAYMENTS.labels("MOMO", "failed").inc()

    db.commit()
    return "ok"
