import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, momo, order_client
from app.database import get_db
from app.models import Payment
from app.processing import PAYMENTS, process_momo_result
from app.schemas import CashConfirm, CreatePaymentOut, PaymentCreate, PaymentOut
from app.security import get_current_user, require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

# Giới hạn số tiền một giao dịch của MoMo (VND)
MOMO_MIN_AMOUNT = 1_000
MOMO_MAX_AMOUNT = 50_000_000


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


# ---------- Khách: tạo giao dịch MoMo ----------
@router.post("/momo/create", response_model=CreatePaymentOut, status_code=201)
def create_momo_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("CUSTOMER")),
):
    order = fetch_order(payload.order_id)

    if order["customer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Không đủ quyền")
    if order["payment_method"] != "MOMO":
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
            detail="MoMo chỉ nhận thanh toán từ 1.000đ đến 50.000.000đ",
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
        method="MOMO",
        amount=amount,
        status="PENDING",
        txn_ref=uuid.uuid4().hex,  # tạm, đổi ngay bên dưới
    )
    db.add(payment)
    db.flush()  # để có payment.id
    # Đuôi ngẫu nhiên: orderId phải là duy nhất trên MoMo, mà key sandbox thì dùng chung
    payment.txn_ref = f"DT{payload.order_id}P{payment.id}-{uuid.uuid4().hex[:10]}"

    if config.MOCK_MODE:
        payment_url = (
            f"{config.PUBLIC_BASE_URL}/api/payments/mock/pay"
            f"?txn_ref={payment.txn_ref}&success=true"
        )
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

    return {
        "order_id": payment.order_id,
        "amount": payment.amount,
        "payment_status": payment.status,  # lấy từ DB, không tin tham số trên URL
        "success": payment.status == "SUCCESS",
        "message": {
            "SUCCESS": "Thanh toán thành công",
            "FAILED": "Thanh toán không thành công",
            "PENDING": "Đang chờ xác nhận từ MoMo",
            "REFUNDED": "Đơn đã hủy, tiền đã được hoàn về ví MoMo",
        }.get(payment.status, payment.status),
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
        "orderId": txn_ref,
        "amount": payment.amount,
        "resultCode": 0 if success else 1006,
        "message": "Giao dịch giả lập",
        "transId": f"MOCK{payment.id}",
        "payType": "mock",
    }
    result = process_momo_result(db, params, skip_signature=True)
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
        raise HTTPException(status_code=400, detail="Đơn này thanh toán qua MoMo")
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
