import time

import httpx

from app import config


class OrderServiceUnavailable(Exception):
    pass


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{config.ORDER_SERVICE_URL}{path}"
    headers = {"X-Internal-Key": config.INTERNAL_KEY}
    last_error = ""
    for attempt in range(3):
        try:
            resp = httpx.request(method, url, headers=headers, timeout=3.0, **kwargs)
            if resp.status_code < 500:
                return resp
            last_error = f"order-service trả {resp.status_code}"
        except httpx.HTTPError as e:
            last_error = str(e)
        if attempt < 2:
            time.sleep(0.3)
    raise OrderServiceUnavailable(last_error)


def get_order(order_id: int) -> tuple[int, dict]:
    resp = _request("GET", f"/internal/orders/{order_id}")
    return resp.status_code, resp.json()


def mark_paid(order_id: int, transaction_ref: str | None) -> tuple[int, dict]:
    resp = _request(
        "POST",
        f"/internal/orders/{order_id}/payment-confirmed",
        json={"transaction_ref": transaction_ref},
    )
    return resp.status_code, resp.json()