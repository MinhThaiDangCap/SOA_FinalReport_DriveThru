import os, time
os.environ.update(
    JWT_SECRET="test", INTERNAL_KEY="ik", PAYMENT_MOCK_MODE="false",
    MOMO_PARTNER_CODE="MOMO", MOMO_ACCESS_KEY="ak", MOMO_SECRET_KEY="sk",
    MOMO_PROCESS_ON_RETURN="false",
)

import jwt, pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, momo, order_client
from app.main import app
from app.database import Base, get_db

ORDER = {"id": 7, "customer_id": 1, "station_id": 1, "payment_method": "MOMO",
         "status": "PENDING_PAYMENT", "total_amount": 45000}


@pytest.fixture()
def ctx(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    calls = {"momo": [], "paid": [], "paid_method": [], "zalopay": [],
             "zp_create": {"return_code": 1, "order_url": "https://qcgateway.zalopay.vn/openinapp?order=x"},
             "zp_query": {"return_code": 3},
             "zp_refund": {"return_code": 1}}

    class FakeResp:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    # momo.httpx và zalopay.httpx là cùng một module: phân biệt theo địa chỉ gọi
    def fake_post(url, json=None, data=None, timeout=None):
        if "zalopay" in url:
            calls["zalopay"].append((url, data))
            key = {"create": "zp_create", "query": "zp_query", "refund": "zp_refund"}[url.rsplit("/", 1)[-1]]
            return FakeResp(calls[key])
        calls["momo"].append((url, json))
        return FakeResp({"resultCode": 0, "payUrl": "https://test-payment.momo.vn/pay/abc"})

    def fake_mark_paid(order_id, ref, method="MOMO"):
        calls["paid"].append((order_id, ref))
        calls["paid_method"].append(method)
        return 200, {}

    monkeypatch.setattr(momo.httpx, "post", fake_post)
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, id=oid)))
    monkeypatch.setattr(order_client, "mark_paid", fake_mark_paid)
    monkeypatch.setattr(config, "PROCESS_ON_RETURN", False)

    app.dependency_overrides[get_db] = override
    yield TestClient(app), calls  # không dùng "with" để khỏi chạy lifespan (kết nối Postgres)
    app.dependency_overrides.clear()


def auth(uid=1, role="CUSTOMER"):
    p = {"sub": str(uid), "role": role, "exp": int(time.time()) + 3600}
    return {"Authorization": "Bearer " + jwt.encode(p, "test", algorithm="HS256")}


def create(client):
    r = client.post("/api/payments/momo/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 201, r.text
    return r.json()


def momo_result(txn_ref, amount=45000, result_code=0, as_text=False):
    """Dựng kết quả giống MoMo gửi về, ký bằng secret key của test."""
    data = {
        "partnerCode": "MOMO", "orderId": txn_ref, "requestId": txn_ref, "amount": amount,
        "orderInfo": "Thanh toan don hang 7", "orderType": "momo_wallet", "transId": 4088878653,
        "resultCode": result_code, "message": "Successful.", "payType": "qr",
        "responseTime": 1721720663942, "extraData": "",
    }
    data["signature"] = momo._sign({k: data[k] for k in momo.RESULT_FIELDS})
    return {k: str(v) for k, v in data.items()} if as_text else data


def status_of(client):
    return client.get("/api/payments/order/7", headers=auth()).json()[-1]["status"]


def test_create_calls_momo_with_valid_signature(ctx):
    client, calls = ctx
    out = create(client)
    assert out["payment_url"] == "https://test-payment.momo.vn/pay/abc"
    assert out["amount"] == 45000

    url, body = calls["momo"][0]
    assert url.endswith("/v2/gateway/api/create")
    assert body["orderId"] == out["txn_ref"] and body["amount"] == 45000
    assert body["ipnUrl"].endswith("/api/payments/momo/ipn")
    signed = {k: v for k, v in body.items() if k not in ("lang", "signature")}
    assert body["signature"] == momo._sign(signed)


def test_create_rejects_wrong_owner_and_cash_order(ctx, monkeypatch):
    client, _ = ctx
    r = client.post("/api/payments/momo/create", json={"order_id": 7}, headers=auth(uid=2))
    assert r.status_code == 403
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, payment_method="CASH")))
    r = client.post("/api/payments/momo/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 400


def test_create_returns_502_when_momo_refuses(ctx, monkeypatch):
    client, _ = ctx

    class Refused:
        def json(self):
            return {"resultCode": 41, "message": "Duplicated orderId"}

    monkeypatch.setattr(momo.httpx, "post", lambda *a, **k: Refused())
    r = client.post("/api/payments/momo/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 502
    assert client.get("/api/payments/order/7", headers=auth()).json() == []


def test_ipn_success_marks_paid_once(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    body = momo_result(txn)

    assert client.post("/api/payments/momo/ipn", json=body).status_code == 204
    assert client.post("/api/payments/momo/ipn", json=body).status_code == 204  # MoMo gửi lại
    assert status_of(client) == "SUCCESS"
    assert calls["paid"] == [(7, "4088878653")]


def test_ipn_with_bad_signature_is_ignored(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    body = momo_result(txn)
    body["signature"] = "0" * 64

    assert client.post("/api/payments/momo/ipn", json=body).status_code == 204
    assert status_of(client) == "PENDING"
    assert calls["paid"] == []


def test_ipn_with_wrong_amount_is_ignored(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    assert client.post("/api/payments/momo/ipn", json=momo_result(txn, amount=1000)).status_code == 204
    assert status_of(client) == "PENDING"
    assert calls["paid"] == []


def test_ipn_failure_marks_failed(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    assert client.post("/api/payments/momo/ipn", json=momo_result(txn, result_code=1006)).status_code == 204
    assert status_of(client) == "FAILED"
    assert calls["paid"] == []


def test_return_only_reads_status_by_default(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    r = client.get("/api/payments/momo/return", params=momo_result(txn, as_text=True))
    assert r.status_code == 200
    assert r.json()["payment_status"] == "PENDING" and calls["paid"] == []


def test_return_processes_result_when_enabled(ctx, monkeypatch):
    client, calls = ctx
    monkeypatch.setattr(config, "PROCESS_ON_RETURN", True)
    txn = create(client)["txn_ref"]
    r = client.get("/api/payments/momo/return", params=momo_result(txn, as_text=True))
    assert r.json()["success"] is True and r.json()["order_id"] == 7
    assert calls["paid"] == [(7, "4088878653")]


def test_return_rejects_tampered_query(ctx):
    client, _ = ctx
    txn = create(client)["txn_ref"]
    params = momo_result(txn, result_code=1006, as_text=True)
    params["resultCode"] = "0"  # khách tự sửa URL thành "thành công"
    assert client.get("/api/payments/momo/return", params=params).status_code == 400


# ---------- Hoàn tiền (order-service gọi khi khách hủy đơn đã trả) ----------
IK = {"X-Internal-Key": "ik"}


def paid_order(client):
    txn = create(client)["txn_ref"]
    assert client.post("/api/payments/momo/ipn", json=momo_result(txn)).status_code == 204
    return txn


def test_refund_calls_momo_and_is_idempotent(ctx):
    client, calls = ctx
    paid_order(client)

    r = client.post("/internal/payments/order/7/refund", headers=IK)
    assert r.status_code == 200
    assert r.json() == {"refunded": True, "amount": 45000, "method": "MOMO"}
    url, body = calls["momo"][-1]
    assert url.endswith("/v2/gateway/api/refund")
    assert body["transId"] == "4088878653" and body["amount"] == 45000
    signed = {k: v for k, v in body.items() if k not in ("lang", "signature")}
    assert body["signature"] == momo._sign(signed)
    assert status_of(client) == "REFUNDED"

    n = len(calls["momo"])
    assert client.post("/internal/payments/order/7/refund", headers=IK).json()["refunded"] is True
    assert len(calls["momo"]) == n  # không hoàn 2 lần


def test_refund_without_payment_and_wrong_key(ctx):
    client, _ = ctx
    assert client.post("/internal/payments/order/7/refund").status_code == 403
    r = client.post("/internal/payments/order/7/refund", headers=IK)
    assert r.json() == {"refunded": False, "amount": 0, "method": None}


def test_refund_rejected_by_momo_keeps_success(ctx, monkeypatch):
    client, _ = ctx
    paid_order(client)

    class Refused:
        def json(self):
            return {"resultCode": 1001, "message": "Refund failed"}

    monkeypatch.setattr(momo.httpx, "post", lambda *a, **k: Refused())
    assert client.post("/internal/payments/order/7/refund", headers=IK).status_code == 502
    assert status_of(client) == "SUCCESS"


# ================= ZaloPay =================
import hashlib, hmac, json as _json

from app import zalopay

ZP_KEY2 = config.ZALOPAY_KEY2


def zp_create(client, order_id=7):
    r = client.post("/api/payments/zalopay/create", json={"order_id": order_id}, headers=auth())
    assert r.status_code == 201, r.text
    return r.json()


def zp_callback(txn_ref, amount=45000, key=None):
    data = _json.dumps({
        "app_id": config.ZALOPAY_APP_ID, "app_trans_id": txn_ref, "app_time": 1, "app_user": "user1",
        "amount": amount, "embed_data": "{}", "item": "[]", "zp_trans_id": 260000123,
        "server_time": 2, "channel": 38, "merchant_user_id": "x", "user_fee_amount": 0,
        "discount_amount": 0,
    })
    mac = hmac.new((key or ZP_KEY2).encode(), data.encode(), hashlib.sha256).hexdigest()
    return {"data": data, "mac": mac, "type": 1}


def zp_redirect(txn_ref, status="1", amount=45000):
    p = {"appid": str(config.ZALOPAY_APP_ID), "apptransid": txn_ref, "pmcid": "38", "bankcode": "",
         "amount": str(amount), "discountamount": "0", "status": status}
    raw = "|".join(p[k] for k in zalopay.REDIRECT_FIELDS)
    p["checksum"] = hmac.new(ZP_KEY2.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return p


def test_zalopay_create_sends_valid_mac(ctx):
    client, calls = ctx
    out = zp_create(client)
    assert out["payment_url"].startswith("https://qcgateway.zalopay.vn/")
    url, body = calls["zalopay"][0]
    assert url.endswith("/v2/create")
    assert body["app_trans_id"] == out["txn_ref"] and body["amount"] == 45000
    assert out["txn_ref"][6] == "_" and len(out["txn_ref"]) <= 40  # yymmdd_...
    assert body["callback_url"].endswith("/api/payments/zalopay/callback")
    raw = "|".join(str(body[k]) for k in
                   ("app_id", "app_trans_id", "app_user", "amount", "app_time", "embed_data", "item"))
    assert body["mac"] == hmac.new(config.ZALOPAY_KEY1.encode(), raw.encode(), hashlib.sha256).hexdigest()
    assert client.get("/api/payments/order/7", headers=auth()).json()[-1]["method"] == "ZALOPAY"


def test_zalopay_create_rejects_cash_order_and_502_on_refusal(ctx, monkeypatch):
    client, calls = ctx
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, payment_method="CASH")))
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 400

    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER)))
    calls["zp_create"] = {"return_code": 2, "sub_return_message": "Chữ ký không hợp lệ"}
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 502
    assert client.get("/api/payments/order/7", headers=auth()).json() == []


def test_momo_order_can_be_paid_with_zalopay(ctx):
    client, calls = ctx  # ORDER chọn MOMO nhưng khách bấm trả bằng ZaloPay
    txn = zp_create(client)["txn_ref"]
    r = client.post("/api/payments/zalopay/callback", json=zp_callback(txn))
    assert r.json()["return_code"] == 1
    assert calls["paid"] == [(7, "260000123")] and calls["paid_method"] == ["ZALOPAY"]


def test_zalopay_callback_success_once(ctx):
    client, calls = ctx
    txn = zp_create(client)["txn_ref"]
    body = zp_callback(txn)
    assert client.post("/api/payments/zalopay/callback", json=body).json()["return_code"] == 1
    assert client.post("/api/payments/zalopay/callback", json=body).json()["return_code"] == 2
    assert status_of(client) == "SUCCESS"
    assert calls["paid"] == [(7, "260000123")]


def test_zalopay_callback_bad_mac_or_amount_ignored(ctx):
    client, calls = ctx
    txn = zp_create(client)["txn_ref"]
    r = client.post("/api/payments/zalopay/callback", json=zp_callback(txn, key="wrong"))
    assert r.json()["return_code"] == -1
    r = client.post("/api/payments/zalopay/callback", json=zp_callback(txn, amount=1000))
    assert r.json()["return_code"] == -1
    assert status_of(client) == "PENDING" and calls["paid"] == []


def test_zalopay_return_queries_zalopay_when_pending(ctx):
    client, calls = ctx
    txn = zp_create(client)["txn_ref"]
    calls["zp_query"] = {"return_code": 1, "amount": 45000, "zp_trans_id": 260000999}
    r = client.get("/api/payments/zalopay/return", params=zp_redirect(txn))
    assert r.status_code == 200 and r.json()["success"] is True and r.json()["method"] == "ZALOPAY"
    assert calls["paid"] == [(7, "260000999")]
    url, body = calls["zalopay"][-1]
    assert url.endswith("/v2/query") and body["app_trans_id"] == txn


def test_zalopay_return_rejects_tampered_query(ctx):
    client, _ = ctx
    txn = zp_create(client)["txn_ref"]
    params = zp_redirect(txn, status="-49")
    params["status"] = "1"  # khách tự sửa URL thành "thành công"
    assert client.get("/api/payments/zalopay/return", params=params).status_code == 400


def test_zalopay_failed_then_late_callback_still_records_payment(ctx):
    client, calls = ctx
    txn = zp_create(client)["txn_ref"]
    calls["zp_query"] = {"return_code": 2, "sub_return_message": "Giao dịch thất bại"}
    r = client.get("/api/payments/zalopay/return", params=zp_redirect(txn, status="-49"))
    assert r.json()["payment_status"] == "FAILED"
    # Khách quay lại app ZaloPay trả xong: tiền về thì vẫn phải ghi nhận
    assert client.post("/api/payments/zalopay/callback", json=zp_callback(txn)).json()["return_code"] == 1
    assert status_of(client) == "SUCCESS"


def test_zalopay_refund_sends_valid_mac(ctx):
    client, calls = ctx
    txn = zp_create(client)["txn_ref"]
    client.post("/api/payments/zalopay/callback", json=zp_callback(txn))

    r = client.post("/internal/payments/order/7/refund", headers=IK)
    assert r.json() == {"refunded": True, "amount": 45000, "method": "ZALOPAY"}
    url, body = calls["zalopay"][-1]
    assert url.endswith("/v2/refund") and body["zp_trans_id"] == "260000123"
    assert body["m_refund_id"].split("_")[1] == str(config.ZALOPAY_APP_ID)
    raw = f"{body['app_id']}|{body['zp_trans_id']}|{body['amount']}|{body['description']}|{body['timestamp']}"
    assert body["mac"] == hmac.new(config.ZALOPAY_KEY1.encode(), raw.encode(), hashlib.sha256).hexdigest()
    assert status_of(client) == "REFUNDED"
