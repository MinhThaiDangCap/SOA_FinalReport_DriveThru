import json
from datetime import datetime, timezone

from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import order_client, vnpay
from app.models import Payment, PaymentCallback

PAYMENTS = Counter(
    "payments_total", "Số giao dịch thanh toán", ["method", "result"]
)


def process_vnpay_result(
    db: Session, params: dict, skip_signature: bool = False
) -> tuple[str, str]:
    txn_ref = params.get("vnp_TxnRef", "")
    valid = True if skip_signature else vnpay.verify(params)
    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))

    # Luôn lưu lại callback (kể cả sai chữ ký) để đối soát
    db.add(
        PaymentCallback(
            payment_id=payment.id if payment else None,
            txn_ref=txn_ref[:60],
            raw_params=json.dumps(params, ensure_ascii=False),
            signature_valid=valid,
            response_code=(params.get("vnp_ResponseCode") or "")[:5] or None,
        )
    )
    db.commit()

    # 1. Chữ ký
    if not valid:
        return "97", "Invalid signature"
    # 2. Đơn tồn tại
    if payment is None:
        return "01", "Order not found"
    # 3. Số tiền khớp (VNPay gửi số tiền x100)
    try:
        paid_amount = int(params.get("vnp_Amount", ""))
    except ValueError:
        return "04", "Invalid amount"
    if paid_amount != payment.amount * 100:
        return "04", "Invalid amount"

    # 4. Khóa dòng để hai IPN đến cùng lúc không xử lý trùng
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment.status != "PENDING":
        return "02", "Order already confirmed"

    success = (
        params.get("vnp_ResponseCode") == "00"
        and params.get("vnp_TransactionStatus") == "00"
    )

    if success:
        ref = params.get("vnp_TransactionNo")
        try:
            code, _ = order_client.mark_paid(payment.order_id, ref)
        except order_client.OrderServiceUnavailable:
            db.rollback()
            return "99", "Order service unavailable"  # VNPay sẽ gọi lại

        if code == 409:
            payment.note = "Đơn đã bị hủy trước khi thanh toán, cần hoàn tiền"
        elif code != 200:
            db.rollback()
            return "99", f"Order service error {code}"

        payment.status = "SUCCESS"
        payment.paid_at = datetime.now(timezone.utc)
        payment.vnp_transaction_no = ref
        payment.bank_code = params.get("vnp_BankCode")
        PAYMENTS.labels("VNPAY", "success").inc()
    else:
        payment.status = "FAILED"
        payment.note = f"VNPay mã lỗi {params.get('vnp_ResponseCode')}"
        PAYMENTS.labels("VNPAY", "failed").inc()

    db.commit()
    return "00", "Confirm Success"