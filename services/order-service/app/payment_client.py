import httpx
from fastapi import HTTPException

from app import config


def is_paid(order_id: int, sync: bool = False) -> bool:
    """Hỏi payment-service đơn đã có giao dịch thành công chưa.

    sync=True: payment-service hỏi lại ZaloPay các giao dịch đang chờ (khách vừa quét mã
    xong mà callback chưa tới). Thấy đã trả thì payment-service gọi ngược lại order-service
    để xác nhận đơn, nên PHẢI gọi trước khi khóa dòng đơn hàng, tránh tự chờ khóa của mình.
    """
    url = f"{config.PAYMENT_SERVICE_URL}/internal/payments/order/{order_id}/paid"
    headers = {"X-Internal-Key": config.INTERNAL_KEY}
    try:
        resp = httpx.get(
            url, headers=headers, params={"sync": "true"} if sync else None, timeout=15.0
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Payment service không phản hồi, chưa kiểm tra được tiền mặt",
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Payment service trả lỗi không mong đợi")
    return bool(resp.json().get("paid"))
