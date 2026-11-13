import hashlib
import hmac
from urllib.parse import quote_plus

from app import config

EXCLUDED = {"vnp_SecureHash", "vnp_SecureHashType"}


def _sign(params: dict) -> tuple[str, str]:
    """Trả về (chuỗi query đã sắp xếp, chữ ký)."""
    items = sorted((k, str(v)) for k, v in params.items() if k not in EXCLUDED)
    query = "&".join(f"{k}={quote_plus(v)}" for k, v in items)
    signature = hmac.new(
        config.VNP_HASH_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return query, signature


def build_payment_url(params: dict) -> str:
    query, signature = _sign(params)
    return f"{config.VNP_URL}?{query}&vnp_SecureHash={signature}"


def verify(params: dict) -> bool:
    """Kiểm tra chữ ký của dữ liệu VNPay gửi về (IPN hoặc return)."""
    given = params.get("vnp_SecureHash", "")
    if not given:
        return False
    vnp_params = {k: v for k, v in params.items() if k.startswith("vnp_")}
    _, expected = _sign(vnp_params)
    return hmac.compare_digest(expected.lower(), given.lower())