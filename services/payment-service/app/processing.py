import json
from datetime import datetime, timezone

from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import momo, order_client, zalopay
from app.models import Payment, PaymentCallback

PAYMENTS = Counter(
    "payments_total", "Số giao dịch thanh toán", ["method", "result"]
)

METHOD_LABEL = {"MOMO": "MoMo", "ZALOPAY": "ZaloPay"}


def _log_callback(
    db: Session, payment: Payment | None, txn_ref: str, raw: dict, valid: bool, code
) -> None:
    """Luôn lưu lại dữ liệu cổng thanh toán gửi về (kể cả sai chữ ký) để đối soát."""
    db.add(
        PaymentCallback(
            payment_id=payment.id if payment else None,
            txn_ref=txn_ref[:60],
            raw_params=json.dumps(raw, ensure_ascii=False),
            signature_valid=valid,
            response_code=str(code if code is not None else "")[:5] or None,
        )
    )
    db.commit()


def _settle(
    db: Session,
    payment: Payment,
    success: bool,
    transaction_ref: str | None,
    bank_code: str | None,
    fail_note: str,
) -> str:
    """Chốt kết quả cuối cùng (thành công/thất bại) của một giao dịch đang PENDING.

    Dùng chung cho MoMo và ZaloPay. Khóa dòng để hai callback đến cùng lúc không xử lý trùng.
    Trả về: ok | already_processed | retry
    """
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # Tiền đã về thì luôn ghi nhận, kể cả khi lần tra cứu trước đã đánh dấu FAILED
    # (khách rời trang ZaloPay rồi mới trả xong trên app); các trường hợp khác chỉ xử lý 1 lần
    if payment.status != "PENDING" and not (success and payment.status == "FAILED"):
        return "already_processed"

    if success:
        try:
            code, _ = order_client.mark_paid(payment.order_id, transaction_ref, payment.method)
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
        payment.transaction_no = transaction_ref
        payment.bank_code = (bank_code or "")[:20] or None
        PAYMENTS.labels(payment.method, "success").inc()
    else:
        payment.status = "FAILED"
        payment.note = fail_note[:200]
        PAYMENTS.labels(payment.method, "failed").inc()

    db.commit()
    return "ok"


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
    _log_callback(db, payment, txn_ref, params, valid, params.get("resultCode"))

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

    # 5. Chốt kết quả
    return _settle(
        db,
        payment,
        success=result_code == momo.SUCCESS_CODE,
        transaction_ref=str(params.get("transId") or "") or None,
        bank_code=str(params.get("payType") or ""),
        fail_note=f"MoMo mã lỗi {result_code}: {params.get('message') or ''}",
    )


def process_zalopay_callback(db: Session, data: str, mac: str) -> str:
    """Xử lý callback ZaloPay (chỉ gửi khi khách trả THÀNH CÔNG). Gọi lại nhiều lần vẫn an toàn.

    Trả về: ok | already_processed | invalid_signature | not_found | invalid_amount | retry
    """
    valid = zalopay.verify_callback(data, mac)
    try:
        info = json.loads(data) if data else {}
        if not isinstance(info, dict):
            info = {}
    except ValueError:
        info = {}

    txn_ref = str(info.get("app_trans_id", ""))
    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref)) if txn_ref else None
    _log_callback(db, payment, txn_ref, {"data": data, "mac": mac}, valid, "1")

    if not valid:
        return "invalid_signature"
    if payment is None:
        return "not_found"
    try:
        paid_amount = int(info.get("amount", ""))
    except (TypeError, ValueError):
        return "invalid_amount"
    if paid_amount != payment.amount:
        return "invalid_amount"

    return _settle(
        db,
        payment,
        success=True,
        transaction_ref=str(info.get("zp_trans_id") or "") or None,
        bank_code=str(info.get("channel") or ""),
        fail_note="",
    )


def sync_zalopay(db: Session, payment: Payment) -> str:
    """Hỏi thẳng ZaloPay trạng thái giao dịch rồi cập nhật (dùng khi callback chưa tới).

    Kết quả lấy từ API server-to-server có ký key1 nên tin được, không cần tham số trên URL.
    Trả về: ok | pending | already_processed | invalid_amount | retry
    """
    if payment.status != "PENDING":
        return "already_processed"
    try:
        body = zalopay.query_order(payment.txn_ref)
    except zalopay.ZaloPayError:
        return "retry"

    code = body.get("return_code")
    _log_callback(db, payment, payment.txn_ref, {"query": body}, True, code)

    if code == zalopay.PROCESSING:
        return "pending"
    if code == zalopay.SUCCESS:
        try:
            if int(body.get("amount", "")) != payment.amount:
                return "invalid_amount"
        except (TypeError, ValueError):
            return "invalid_amount"
        return _settle(
            db,
            payment,
            success=True,
            transaction_ref=str(body.get("zp_trans_id") or "") or None,
            bank_code="",
            fail_note="",
        )
    # Đơn ZaloPay chưa thanh toán (khách hủy, hết hạn...): sub_return_code âm
    return _settle(
        db,
        payment,
        success=False,
        transaction_ref=None,
        bank_code=None,
        fail_note=f"ZaloPay: {body.get('sub_return_message') or body.get('return_message') or code}",
    )
