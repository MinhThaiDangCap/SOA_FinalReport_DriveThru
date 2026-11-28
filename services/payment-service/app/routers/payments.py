import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, order_client, zalopay
from app.database import get_db
from app.models import Payment
from app.processing import PAYMENTS, process_zalopay_callback, settle, sync_zalopay
from app.schemas import CashConfirm, CreatePaymentOut, PaymentCreate, PaymentOut
from app.security import get_current_user, require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# Giới hạn số tiền một giao dịch ZaloPay (VND)
ZALOPAY_MIN_AMOUNT = 1_000
ZALOPAY_MAX_AMOUNT = 50_000_000


# ---------- Hàm dùng chung ----------
def fetch_order(order_id: int) -> dict:
    try:
        code, body = order_client.get_order(order_id)
    except order_client.OrderServiceUnavailable:
        raise HTTPException(
            status_code=503, detail="Order service không phản hồi, vui lòng thử lại sau"
        )
    if code == 404:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    if code != 200:
        raise HTTPException(status_code=502, detail="Order service trả lỗi không mong đợi")
    return body


def result_body(payment: Payment) -> dict:
    """Kết quả hiển thị trên trang /payment/result, lấy từ DB, không tin tham số trên URL."""
    return {
        "order_id": payment.order_id,
        "amount": payment.amount,
        "method": payment.method,
        "payment_status": payment.status,
        "success": payment.status == "SUCCESS",
        "message": {
            "SUCCESS": "Thanh toán thành công",
            "FAILED": "Thanh toán không thành công",
            "PENDING": "Đang chờ xác nhận từ ZaloPay",
        }.get(payment.status, payment.status),
    }


# ---------- Khách: tạo giao dịch ZaloPay ----------
@router.post("/zalopay/create", response_model=CreatePaymentOut, status_code=201)
def create_zalopay_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    order = fetch_order(payload.order_id)

    if order["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    # Khách chỉ trả tiền khi đã tới trạm 1 và nhân viên đã nhận đơn (AWAITING_PAYMENT).
    # PENDING_PAYMENT: đơn cũ của cách làm trước (trả ngay khi đặt).
    if order["status"] == "HOLD":
        raise HTTPException(
            status_code=409,
            detail="Vui lòng tới trạm 1 và đọc mã đơn cho nhân viên trước khi thanh toán",
        )
    if order["status"] not in ("AWAITING_PAYMENT", "PENDING_PAYMENT"):
        raise HTTPException(
            status_code=409,
            detail=f"Đơn đang ở trạng thái {order['status']}, không thể thanh toán",
        )
    if order["payment_method"] != "ZALOPAY":
        raise HTTPException(status_code=400, detail="Đơn này chọn trả tiền mặt tại trạm 1")
    amount = order["total_amount"]
    if not ZALOPAY_MIN_AMOUNT <= amount <= ZALOPAY_MAX_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail="ZaloPay chỉ nhận thanh toán từ 1.000đ đến 50.000.000đ",
        )

    already_paid = db.scalar(
        select(Payment).where(
            Payment.order_id == payload.order_id, Payment.status == "SUCCESS"
        )
    )
    if already_paid:
        raise HTTPException(status_code=409, detail="Đơn đã được thanh toán")

    # Mỗi lần bấm thanh toán là một giao dịch mới (khách có thể thử lại nếu lần trước lỗi)
    payment = Payment(
        order_id=payload.order_id,
        customer_id=user["id"],
        method="ZALOPAY",
        amount=amount,
        status="PENDING",
        txn_ref=uuid.uuid4().hex,  # tạm, đổi ngay bên dưới
    )
    db.add(payment)
    db.flush()  # để có payment.id
    # app_trans_id = yymmdd_<mã riêng>; đuôi ngẫu nhiên vì app_id sandbox dùng chung
    payment.txn_ref = zalopay.make_trans_id(
        f"DT{payload.order_id}P{payment.id}x{uuid.uuid4().hex[:8]}"
    )

    if config.MOCK_MODE:
        payment_url = (
            f"{config.PUBLIC_BASE_URL}/api/payments/mock/pay"
            f"?txn_ref={payment.txn_ref}&success=true"
        )
    else:
        try:
            payment_url = zalopay.create_order(
                payment.txn_ref,
                amount,
                f"GoLane - Thanh toan don hang #{payload.order_id}",
                app_user=f"user{user['id']}",
            )
        except zalopay.ZaloPayError as e:
            db.rollback()
            logger.error("Tạo giao dịch ZaloPay thất bại: %s", e)
            raise HTTPException(
                status_code=502,
                detail="Không tạo được giao dịch ZaloPay, vui lòng thử lại",
            )

    db.commit()
    return CreatePaymentOut(
        payment_id=payment.id,
        txn_ref=payment.txn_ref,
        amount=amount,
        payment_url=payment_url,
    )


# ---------- ZaloPay gọi về khi khách trả thành công (server-to-server, POST JSON) ----------
@router.post("/zalopay/callback")
async def zalopay_callback(request: Request, db: Session = Depends(get_db)):
    """ZaloPay yêu cầu trả JSON {return_code, return_message}:
    1 = đã nhận, 2 = trùng (đã xử lý rồi), -1 = dữ liệu sai, 0 = lỗi tạm, ZaloPay gửi lại.
    """
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("body không phải object")
    except ValueError:
        return {"return_code": -1, "return_message": "invalid body"}

    try:
        result = process_zalopay_callback(
            db, str(body.get("data") or ""), str(body.get("mac") or "")
        )
    except Exception:
        logger.exception("Lỗi khi xử lý callback ZaloPay")
        db.rollback()
        result = "retry"

    if result != "ok":
        logger.warning("Callback ZaloPay: %s", result)
    codes = {"ok": 1, "already_processed": 2, "retry": 0}
    return {"return_code": codes.get(result, -1), "return_message": result}


# ---------- Khách quay về từ ZaloPay: web gọi API này để hiển thị kết quả ----------
@router.get("/zalopay/return")
def zalopay_return(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    txn_ref = params.get("apptransid", "")

    if not config.MOCK_MODE and not zalopay.verify_redirect(params):
        raise HTTPException(status_code=400, detail="Chữ ký không hợp lệ")

    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if payment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    # Callback chưa tới (chạy local không có ngrok, hoặc ZaloPay gửi chậm):
    # hỏi thẳng ZaloPay bằng API tra cứu có ký, idempotent nên gọi lại cũng an toàn
    if payment.status == "PENDING" and not config.MOCK_MODE:
        sync_zalopay(db, payment)
        db.refresh(payment)

    return result_body(payment)


# ---------- Thanh toán giả (chỉ chạy khi PAYMENT_MOCK_MODE=true) ----------
@router.get("/mock/pay")
def mock_pay(txn_ref: str, success: bool = True, db: Session = Depends(get_db)):
    if not config.MOCK_MODE:
        raise HTTPException(status_code=404, detail="Not Found")

    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if payment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    result = settle(
        db,
        payment,
        success=success,
        transaction_ref=f"MOCK{payment.id}",
        bank_code="mock",
        fail_note="Giao dịch giả lập thất bại",
    )
    db.refresh(payment)
    return {"result": result, "payment_status": payment.status}


# ---------- Trạm 1: xác nhận đã thu tiền mặt, đơn vào bếp ----------
# Đơn cũ (cách làm trước) thu tiền mặt lúc giao món: chỉ ghi nhận, không báo vào bếp
LEGACY_CASH_STATUSES = ("CONFIRMED", "PREPARING", "READY", "ARRIVED")


def _send_to_kitchen(order_id: int, txn_ref: str) -> None:
    """Báo order-service đã thu tiền mặt: đơn chuyển sang CONFIRMED, vào hàng đợi bếp."""
    try:
        code, _ = order_client.mark_paid(order_id, txn_ref, "CASH")
    except order_client.OrderServiceUnavailable:
        raise HTTPException(
            status_code=503, detail="Order service không phản hồi, vui lòng bấm lại"
        )
    if code != 200:
        raise HTTPException(status_code=409, detail="Không đưa được đơn vào bếp")


@router.post("/cash/confirm", response_model=PaymentOut)
def confirm_cash(
    payload: CashConfirm,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    order = fetch_order(payload.order_id)

    if user["role"] == "STAFF" and user["station_id"] != order["station_id"]:
        raise HTTPException(status_code=403, detail="Đơn này thuộc cửa hàng khác")
    if order["status"] == "HOLD":
        raise HTTPException(
            status_code=409, detail="Đơn chưa được nhận ở trạm 1, hãy bấm Nhận đơn trước"
        )
    new_flow = order["status"] == "AWAITING_PAYMENT"
    if not new_flow and order["status"] not in LEGACY_CASH_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Không thể thu tiền đơn đang ở trạng thái {order['status']}",
        )
    if order["payment_method"] != "CASH":
        raise HTTPException(status_code=400, detail="Đơn này thanh toán qua ZaloPay")

    txn_ref = f"CASH{payload.order_id}"
    existing = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if existing:
        # Gọi lại nhiều lần vẫn an toàn; lần trước báo bếp lỗi thì báo lại
        if new_flow:
            _send_to_kitchen(payload.order_id, txn_ref)
        return existing

    payment = Payment(
        order_id=payload.order_id,
        customer_id=order["customer_id"],
        method="CASH",
        amount=order["total_amount"],
        status="SUCCESS",
        txn_ref=txn_ref,
        collected_by=user["id"],
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:  # hai nhân viên bấm cùng lúc
        db.rollback()
        return db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    db.refresh(payment)
    PAYMENTS.labels("CASH", "success").inc()
    if new_flow:
        _send_to_kitchen(payload.order_id, txn_ref)
    return payment


# ---------- Xem các giao dịch của một đơn ----------
@router.get("/order/{order_id}", response_model=list[PaymentOut])
def payments_of_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(Payment).where(Payment.order_id == order_id).order_by(Payment.id)
    if user["role"] == "CUSTOMER":
        stmt = stmt.where(Payment.customer_id == user["id"])
    return db.scalars(stmt).all()
