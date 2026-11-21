"""Gọi API ZaloPay v2 (tạo đơn, tra cứu) và kiểm tra dữ liệu ZaloPay gửi về.

Tài liệu: https://docs.zalopay.vn (Gateway / Payment). Mọi yêu cầu gửi đi ký HMAC-SHA256
bằng key1; callback và redirect ZaloPay gửi về được ký bằng key2.

Hoàn tiền không nằm trong phạm vi hệ thống: đơn đã thanh toán muốn hủy thì khách liên hệ
hotline, cửa hàng hủy và hoàn tiền trên trang quản lý của ZaloPay.
"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import httpx

from app import config

# return_code của ZaloPay: 1 = thành công, 2 = thất bại, 3 = đang xử lý
SUCCESS = 1
FAILED = 2
PROCESSING = 3

# app_trans_id phải bắt đầu bằng ngày theo giờ Việt Nam (yymmdd_)
VN_TZ = timezone(timedelta(hours=7))


class ZaloPayError(Exception):
    """ZaloPay không phản hồi hoặc từ chối yêu cầu."""


def _hmac(key: str, raw: str) -> str:
    return hmac.new(key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _post(path: str, data: dict, timeout: float = 10.0) -> dict:
    try:
        resp = httpx.post(f"{config.ZALOPAY_ENDPOINT}{path}", data=data, timeout=timeout)
        body = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ZaloPayError(f"Không gọi được ZaloPay: {e}")
    if not isinstance(body, dict):
        raise ZaloPayError("ZaloPay trả dữ liệu không hợp lệ")
    return body


def _describe(body: dict) -> str:
    return (
        f"[{body.get('return_code')}/{body.get('sub_return_code')}] "
        f"{body.get('sub_return_message') or body.get('return_message')}"
    )


def make_trans_id(suffix: str) -> str:
    """app_trans_id = yymmdd_<mã riêng>, ngày theo giờ Việt Nam, tối đa 40 ký tự."""
    return f"{datetime.now(VN_TZ):%y%m%d}_{suffix}"[:40]


def create_order(app_trans_id: str, amount: int, description: str, app_user: str) -> str:
    """Tạo đơn trên ZaloPay, trả về order_url (trang thanh toán có QR, ATM, thẻ, ví)."""
    app_time = int(time.time() * 1000)
    # preferred_payment_method rỗng = trang ZaloPay hiện đủ các cách trả (QR ví, ATM, thẻ)
    embed_data = json.dumps(
        {"redirecturl": config.ZALOPAY_REDIRECT_URL, "preferred_payment_method": []}
    )
    item = "[]"
    data = {
        "app_id": config.ZALOPAY_APP_ID,
        "app_user": app_user,
        "app_trans_id": app_trans_id,
        "app_time": app_time,
        "amount": amount,
        "item": item,
        "embed_data": embed_data,
        "description": description,
        "bank_code": "",
        "callback_url": config.ZALOPAY_CALLBACK_URL,
    }
    data["mac"] = _hmac(
        config.ZALOPAY_KEY1,
        f"{config.ZALOPAY_APP_ID}|{app_trans_id}|{app_user}|{amount}|{app_time}|{embed_data}|{item}",
    )

    body = _post("/v2/create", data)
    if body.get("return_code") != SUCCESS or not body.get("order_url"):
        raise ZaloPayError(f"ZaloPay từ chối tạo đơn: {_describe(body)}")
    return body["order_url"]


def query_order(app_trans_id: str) -> dict:
    """Hỏi ZaloPay trạng thái đơn. Trả nguyên body (return_code, amount, zp_trans_id...)."""
    data = {
        "app_id": config.ZALOPAY_APP_ID,
        "app_trans_id": app_trans_id,
        "mac": _hmac(
            config.ZALOPAY_KEY1,
            f"{config.ZALOPAY_APP_ID}|{app_trans_id}|{config.ZALOPAY_KEY1}",
        ),
    }
    return _post("/v2/query", data)


def verify_callback(data: str, mac: str) -> bool:
    """Callback: mac = HMAC(key2, data), data là chuỗi JSON nguyên văn ZaloPay gửi."""
    if not data or not mac:
        return False
    return hmac.compare_digest(_hmac(config.ZALOPAY_KEY2, data), str(mac).lower())


REDIRECT_FIELDS = ("appid", "apptransid", "pmcid", "bankcode", "amount", "discountamount", "status")


def verify_redirect(params: dict) -> bool:
    """Redirect về web: checksum = HMAC(key2, appid|apptransid|pmcid|bankcode|amount|discountamount|status)."""
    given = str(params.get("checksum") or "")
    if not given:
        return False
    raw = "|".join(str(params.get(k, "")) for k in REDIRECT_FIELDS)
    return hmac.compare_digest(_hmac(config.ZALOPAY_KEY2, raw), given.lower())
