import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, order_client, vnpay
from app.database import get_db
from app.models import Payment
from app.processing import PAYMENTS, process_vnpay_result
from app.schemas import CashConfirm, CreatePaymentOut, PaymentCreate, PaymentOut
from app.security import get_current_user, require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])


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


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "127.0.0.1")
    )
    return "127.0.0.1" if ":" in ip else ip  # VNPay chỉ nhận IPv4


# ---------- Khách: tạo link thanh toán VNPay ----------
@router.post("/vnpay/create", response_model=CreatePaymentOut, status_code=201)
def create_vnpay_payment(
    payload: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    order = fetch_order(payload.order_id)

    if order["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    if order["payment_method"] != "VNPAY":
        raise HTTPException(status_code=400, detail="Đơn này chọn trả tại quầy")
    if order["status"] != "PENDING_PAYMENT":
        raise HTTPException(
            status_code=409,
            detail=f"Đơn đang ở trạng thái {order['status']}, không thể thanh toán",
        )
    amount = order["total_amount"]
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Số tiền thanh toán không hợp lệ")

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
        method="VNPAY",
        amount=amount,
        status="PENDING",
        txn_ref=uuid.uuid4().hex,  # tạm, đổi ngay bên dưới
    )
    db.add(payment)
    db.flush()  # để có payment.id
    payment.txn_ref = f"ORD{payload.order_id}P{payment.id}"

    if config.MOCK_MODE:
        payment_url = (
            f"{config.PUBLIC_BASE_URL}/api/payments/mock/pay"
            f"?txn_ref={payment.txn_ref}&success=true"
        )
    else:
        now = datetime.now(timezone(timedelta(hours=7)))  # VNPay dùng giờ GMT+7
        params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": config.VNP_TMN_CODE,
            "vnp_Amount": str(amount * 100),
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": payment.txn_ref,
            "vnp_OrderInfo": f"Thanh toan don hang {payload.order_id}",  # không dấu
            "vnp_OrderType": "other",
            "vnp_Locale": "vn",
            "vnp_ReturnUrl": config.VNP_RETURN_URL,
            "vnp_IpAddr": client_ip(request),
            "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
            "vnp_ExpireDate": (now + timedelta(minutes=15)).strftime("%Y%m%d%H%M%S"),
        }
        payment_url = vnpay.build_payment_url(params)

    db.commit()
    return CreatePaymentOut(
        payment_id=payment.id,
        txn_ref=payment.txn_ref,
        amount=amount,
        payment_url=payment_url,
    )


# ---------- VNPay gọi về (server-to-server) ----------
@router.get("/vnpay/ipn")
def vnpay_ipn(request: Request, db: Session = Depends(get_db)):
    try:
        code, message = process_vnpay_result(db, dict(request.query_params))
    except Exception:
        logger.exception("Lỗi khi xử lý IPN")
        db.rollback()
        code, message = "99", "Unknown error"
    return {"RspCode": code, "Message": message}  # luôn HTTP 200 theo yêu cầu VNPay


# ---------- Khách quay về từ VNPay: web gọi API này để hiển thị kết quả ----------
@router.get("/vnpay/return")
def vnpay_return(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    txn_ref = params.get("vnp_TxnRef", "")

    if not config.MOCK_MODE:
        if not vnpay.verify(params):
            raise HTTPException(status_code=400, detail="Chữ ký không hợp lệ")
        if config.PROCESS_ON_RETURN:
            process_vnpay_result(db, params)  # idempotent, xử lý lại cũng an toàn

    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if payment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    return {
        "order_id": payment.order_id,
        "amount": payment.amount,
        "payment_status": payment.status,  # lấy từ DB, không tin tham số trên URL
        "success": payment.status == "SUCCESS",
        "message": {
            "SUCCESS": "Thanh toán thành công",
            "FAILED": "Thanh toán không thành công",
            "PENDING": "Đang chờ xác nhận từ VNPay",
        }[payment.status],
    }


# ---------- Thanh toán giả (chỉ chạy khi PAYMENT_MOCK_MODE=true) ----------
@router.get("/mock/pay")
def mock_pay(txn_ref: str, success: bool = True, db: Session = Depends(get_db)):
    if not config.MOCK_MODE:
        raise HTTPException(status_code=404, detail="Not Found")

    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if payment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    params = {
        "vnp_TxnRef": txn_ref,
        "vnp_Amount": str(payment.amount * 100),
        "vnp_ResponseCode": "00" if success else "24",
        "vnp_TransactionStatus": "00" if success else "02",
        "vnp_TransactionNo": f"MOCK{payment.id}",
        "vnp_BankCode": "MOCK",
    }
    code, message = process_vnpay_result(db, params, skip_signature=True)
    db.refresh(payment)
    return {"RspCode": code, "Message": message, "payment_status": payment.status}


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
        raise HTTPException(status_code=400, detail="Đơn này thanh toán qua VNPay")
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