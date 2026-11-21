import httpx
from fastapi import HTTPException

from app import config


def is_paid(order_id: int) -> bool:
    """Hỏi payment-service đơn đã có giao dịch thành công chưa (dùng cho đơn tiền mặt)."""
    url = f"{config.PAYMENT_SERVICE_URL}/internal/payments/order/{order_id}/paid"
    headers = {"X-Internal-Key": config.INTERNAL_KEY}
    try:
        resp = httpx.get(url, headers=headers, timeout=3.0)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Payment service không phản hồi, chưa kiểm tra được tiền mặt",
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Payment service trả lỗi không mong đợi")
    return bool(resp.json().get("paid"))


def refund_order(order_id: int) -> dict:
    """Nhờ payment-service hoàn tiền online (MoMo/ZaloPay) của đơn.

    Trả {"refunded": bool, "amount": int, "method": "MOMO" | "ZALOPAY" | None}.

    Không retry: payment-service tự đảm bảo gọi lại an toàn, khách bấm hủy lần nữa là được.
    Lỗi thì ném HTTPException để KHÔNG hủy đơn khi tiền chưa được hoàn.
    """
    url = f"{config.PAYMENT_SERVICE_URL}/internal/payments/order/{order_id}/refund"
    headers = {"X-Internal-Key": config.INTERNAL_KEY}
    try:
        resp = httpx.post(url, headers=headers, timeout=35.0)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Chưa hoàn tiền được vì payment service không phản hồi, vui lòng thử lại sau",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Ví chưa hoàn tiền được nên đơn chưa bị hủy, vui lòng thử lại sau",
        )
    return resp.json()
