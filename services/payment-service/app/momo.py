import hashlib
import hmac

import httpx

from app import config

# resultCode của MoMo: 0 = thành công; các mã dưới đây = giao dịch còn đang xử lý
SUCCESS_CODE = 0
PENDING_CODES = {1000, 7000, 7002}

# Các trường tham gia ký trong kết quả MoMo gửi về (IPN và redirect)
RESULT_FIELDS = (
    "amount", "extraData", "message", "orderId", "orderInfo", "orderType",
    "partnerCode", "payType", "requestId", "responseTime", "resultCode", "transId",
)


class MomoError(Exception):
    """MoMo không phản hồi hoặc từ chối tạo giao dịch."""


def _sign(fields: dict) -> str:
    """HMAC-SHA256 trên chuỗi key=value nối bằng &, key xếp theo a-z, không URL-encode."""
    data = {"accessKey": config.MOMO_ACCESS_KEY, **fields}
    raw = "&".join(f"{k}={data[k]}" for k in sorted(data))
    return hmac.new(
        config.MOMO_SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_payment(txn_ref: str, amount: int, order_info: str) -> str:
    """Gọi API tạo giao dịch của MoMo, trả về payUrl để chuyển khách sang thanh toán."""
    fields = {
        "amount": amount,
        "extraData": "",
        "ipnUrl": config.MOMO_IPN_URL,
        "orderId": txn_ref,
        "orderInfo": order_info,
        "partnerCode": config.MOMO_PARTNER_CODE,
        "redirectUrl": config.MOMO_REDIRECT_URL,
        "requestId": txn_ref,
        "requestType": config.MOMO_REQUEST_TYPE,
    }
    body = {**fields, "lang": "vi", "signature": _sign(fields)}

    try:
        resp = httpx.post(
            f"{config.MOMO_ENDPOINT}/v2/gateway/api/create", json=body, timeout=10.0
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise MomoError(f"Không gọi được MoMo: {e}")

    if data.get("resultCode") != SUCCESS_CODE or not data.get("payUrl"):
        raise MomoError(
            f"MoMo từ chối tạo giao dịch: [{data.get('resultCode')}] {data.get('message')}"
        )
    return data["payUrl"]


def verify(params: dict) -> bool:
    """Kiểm tra chữ ký của kết quả MoMo gửi về (IPN hoặc redirect)."""
    given = str(params.get("signature") or "")
    if not given:
        return False
    expected = _sign({k: params.get(k, "") for k in RESULT_FIELDS})
    return hmac.compare_digest(expected, given.lower())
