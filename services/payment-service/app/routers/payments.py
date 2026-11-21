import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, momo, order_client, zalopay
from app.database import get_db
from app.models import Payment
from app.processing import (
    METHOD_LABEL,
    PAYMENTS,
    _settle,
    process_momo_result,
    process_zalopay_callback,
    sync_zalopay,
)
from app.schemas import CashConfirm, CreatePaymentOut, PaymentCreate, PaymentOut
from app.security import get_current_user, require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# Giới hạn số tiền một giao dịch online (VND), theo mức chung của MoMo và ZaloPay
MOMO_MIN_AMOUNT = 1_000
MOMO_MAX_AMOUNT = 50_000_000
# Đơn chọn một trong các cách này là đơn trả online (phải thanh toán trước khi vào bếp)
ONLINE_METHODS = ("MOMO", "ZALOPAY")


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


def start_online_payment(
    payload: PaymentCreate, db: Session, user: dict, method: str
) -> tuple[Payment, int]:
    """Kiểm tra đơn rồi tạo bản ghi giao dịch PENDING (chưa commit). Dùng chung MoMo/ZaloPay.

    Đơn trả online (MOMO hoặc ZALOPAY) chưa thanh toán thì trả bằng ví nào cũng được:
    khi tiền về, order-service ghi lại đúng ví khách đã dùng.
    """
    order = fetch_order(payload.order_id)
    label = METHOD_LABEL[method]

    if order["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    if order["payment_method"] not in ONLINE_METHODS:
        raise HTTPException(status_code=400, detail="Đơn này chọn trả tại quầy")
    if order["status"] != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=409,
            detail=f"Đơn đang ở trạng thái {order['status']}, không thể thanh toán",
        )
    amount = order["total_amount"]
    if not MOMO_MIN_AMOUNT <= amount <= MOMO_MAX_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"{label} chỉ nhận thanh toán từ 1.000đ đến 50.000.000đ",
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
        method=method,
        amount=amount,
        status="PENDING",
        txn_ref=uuid.uuid4().hex,  # tạm, đổi ngay sau khi có payment.id
    )
    db.add(payment)
    db.flush()  # để có payment.id
    return payment, amount


def mock_url(txn_ref: str) -> str:
    return f"{config.PUBLIC_BASE_URL}/api/payments/mock/pay?txn_ref={txn_ref}&success=true"


# ---------- Khách: tạo giao dịch MoMo ----------
@router.post("/momo/create", response_model=CreatePaymentOut, status_code=201)
def create_momo_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    payment, amount = start_online_payment(payload, db, user, "MOMO")
    # Đuôi ngẫu nhiên: orderId phải là duy nhất trên MoMo, mà key sandbox thì dùng chung
    payment.txn_ref = f"DT{payload.order_id}P{payment.id}-{uuid.uuid4().hex[:10]}"

    if config.MOCK_MODE:
        payment_url = mock_url(payment.txn_ref)
    else:
        try:
            payment_url = momo.create_payment(
                payment.txn_ref, amount, f"Thanh toan don hang {payload.order_id}"
            )
        except momo.MomoError as e:
            db.rollback()
            logger.error("Tạo giao dịch MoMo thất bại: %s", e)
            raise HTTPException(
                status_code=502,
                detail="Không tạo được giao dịch MoMo, vui lòng thử lại",
            )

    db.commit()
    return CreatePaymentOut(
        payment_id=payment.id,
        txn_ref=payment.txn_ref,
        amount=amount,
        payment_url=payment_url,
    )


# ---------- Khách: tạo giao dịch ZaloPay ----------
@router.post("/zalopay/create", response_model=CreatePaymentOut, status_code=201)
def create_zalopay_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    payment, amount = start_online_payment(payload, db, user, "ZALOPAY")
    # app_trans_id = yymmdd_<mã riêng>; đuôi ngẫu nhiên vì app_id sandbox dùng chung
    payment.txn_ref = zalopay.make_trans_id(
        f"DT{payload.order_id}P{payment.id}x{uuid.uuid4().hex[:8]}"
    )

    if config.MOCK_MODE:
        payment_url = mock_url(payment.txn_ref)
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


# ---------- MoMo gọi về (server-to-server, POST JSON) ----------
@router.post("/momo/ipn", status_code=204)
async def momo_ipn(request: Request, db: Session = Depends(get_db)):
    try:
        params = await request.json()
        if not isinstance(params, dict):
            raise ValueError("body không phải object")
    except ValueError:
        raise HTTPException(status_code=400, detail="Dữ liệu không hợp lệ")

    try:
        result = process_momo_result(db, params)
    except Exception:
        logger.exception("Lỗi khi xử lý IPN MoMo")
        db.rollback()
        result = "retry"

    if result == "retry":
        raise HTTPException(status_code=503, detail="Tạm thời chưa xử lý được")
    if result != "ok":
        logger.warning("IPN MoMo %s: %s", params.get("orderId"), result)
    return Response(status_code=204)  # MoMo yêu cầu trả 204, không có nội dung


# ---------- Khách quay về từ MoMo: web gọi API này để hiển thị kết quả ----------
@router.get("/momo/return")
def momo_return(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    txn_ref = params.get("orderId", "")

    if not config.MOCK_MODE:
        if not momo.verify(params):
            raise HTTPException(status_code=400, detail="Chữ ký không hợp lệ")
        if config.PROCESS_ON_RETURN:
            process_momo_result(db, params)  # idempotent, xử lý lại cũng an toàn

    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if payment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    return result_body(payment)


def result_body(payment: Payment) -> dict:
    """Kết quả hiển thị trên trang /payment/result, lấy từ DB, không tin tham số trên URL."""
    label = METHOD_LABEL.get(payment.method, payment.method)
    return {
        "order_id": payment.order_id,
        "amount": payment.amount,
        "method": payment.method,
        "payment_status": payment.status,
        "success": payment.status == "SUCCESS",
        "message": {
            "SUCCESS": "Thanh toán thành công",
            "FAILED": "Thanh toán không thành công",
            "PENDING": f"Đang chờ xác nhận từ {label}",
            "REFUNDED": f"Đơn đã hủy, tiền đã được hoàn về ví {label}",
        }.get(payment.status, payment.status),
    }


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

    if payment.method == "MOMO":
        params = {
            "orderId": txn_ref,
            "amount": payment.amount,
            "resultCode": 0 if success else 1006,
            "message": "Giao dịch giả lập",
            "transId": f"MOCK{payment.id}",
            "payType": "mock",
        }
        result = process_momo_result(db, params, skip_signature=True)
    else:
        result = _settle(
            db,
            payment,
            success=success,
            transaction_ref=f"MOCK{payment.id}",
            bank_code="mock",
            fail_note="Giao dịch giả lập thất bại",
        )
    db.refresh(payment)
    return {"result": result, "payment_status": payment.status}


# ---------- Nhân viên: xác nhận đã thu tiền tại quầy ----------
@router.post("/cash/confirm", response_model=PaymentOut)
def confirm_cash(
    payload: CashConfirm,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    order = fetch_order(payload.order_id)

    if user["role"] == "STAFF" and user["station_id"] != order["station_id"]:
        raise HTTPException(status_code=403, detail="Đơn này thuộc cửa hàng khác")
    if order["payment_method"] != "CASH":
        raise HTTPException(status_code=400, detail="Đơn này thanh toán online")
    if order["status"] in ("PENDING_PAYMENT", "CANCELLED"):
        raise HTTPException(
            status_code=409,
            detail=f"Không thể thu tiền đơn đang ở trạng thái {order['status']}",
        )

    txn_ref = f"CASH{payload.order_id}"
    existing = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if existing:
        return existing  # gọi lại nhiều lần vẫn an toàn

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
