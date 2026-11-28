import os, time
os.environ.update(JWT_SECRET="test", INTERNAL_KEY="ik", PAYMENT_MOCK_MODE="false")

import hashlib, hmac, json

import jwt, pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, order_client, zalopay
from app.main import app
from app.database import Base, get_db

ORDER = {"id": 7, "customer_id": 1, "station_id": 1, "payment_method": "ZALOPAY",
         "status": "PENDING_PAYMENT", "total_amount": 45000}
IK = {"X-Internal-Key": "ik"}


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

    calls = {"zalopay": [], "paid": [],
             "create": {"return_code": 1, "order_url": "https://qcgateway.zalopay.vn/openinapp?order=x"},
             "query": {"return_code": 3}}

    class FakeResp:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    def fake_post(url, data=None, timeout=None):
        calls["zalopay"].append((url, data))
        return FakeResp(calls[url.rsplit("/", 1)[-1]])

    def fake_mark_paid(order_id, ref, method=None):
        calls["paid"].append((order_id, ref))
        calls.setdefault("paid_method", []).append(method)
        return 200, {}

    monkeypatch.setattr(zalopay.httpx, "post", fake_post)
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, id=oid)))
    monkeypatch.setattr(order_client, "mark_paid", fake_mark_paid)

    app.dependency_overrides[get_db] = override
    yield TestClient(app), calls  # không dùng "with" để khỏi chạy lifespan (kết nối Postgres)
    app.dependency_overrides.clear()


def auth(uid=1, role="CUSTOMER", station=None):
    p = {"sub": str(uid), "role": role, "exp": int(time.time()) + 3600}
    if station:
        p["station_id"] = station
    return {"Authorization": "Bearer " + jwt.encode(p, "test", algorithm="HS256")}


def create(client):
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 201, r.text
    return r.json()


def status_of(client):
    return client.get("/api/payments/order/7", headers=auth()).json()[-1]["status"]


def sign(key, raw):
    return hmac.new(key.encode(), raw.encode(), hashlib.sha256).hexdigest()


def callback(txn_ref, amount=45000, key=None):
    """Dựng callback giống ZaloPay gửi về, ký bằng key2."""
    data = json.dumps({
        "app_id": config.ZALOPAY_APP_ID, "app_trans_id": txn_ref, "app_time": 1, "app_user": "user1",
        "amount": amount, "embed_data": "{}", "item": "[]", "zp_trans_id": 260000123,
        "server_time": 2, "channel": 38, "merchant_user_id": "x", "user_fee_amount": 0,
        "discount_amount": 0,
    })
    return {"data": data, "mac": sign(key or config.ZALOPAY_KEY2, data), "type": 1}


def redirect(txn_ref, status="1", amount=45000):
    """Dựng tham số ZaloPay gắn lên URL khi chuyển khách về web, ký bằng key2."""
    p = {"appid": str(config.ZALOPAY_APP_ID), "apptransid": txn_ref, "pmcid": "38", "bankcode": "",
         "amount": str(amount), "discountamount": "0", "status": status}
    p["checksum"] = sign(config.ZALOPAY_KEY2, "|".join(p[k] for k in zalopay.REDIRECT_FIELDS))
    return p


# ---------- Tạo giao dịch ----------
def test_create_sends_valid_mac(ctx):
    client, calls = ctx
    out = create(client)
    assert out["payment_url"].startswith("https://qcgateway.zalopay.vn/")
    assert out["amount"] == 45000

    url, body = calls["zalopay"][0]
    assert url.endswith("/v2/create")
    assert body["app_trans_id"] == out["txn_ref"] and body["amount"] == 45000
    assert out["txn_ref"][6] == "_" and len(out["txn_ref"]) <= 40  # yymmdd_...
    assert body["callback_url"].endswith("/api/payments/zalopay/callback")
    raw = "|".join(str(body[k]) for k in
                   ("app_id", "app_trans_id", "app_user", "amount", "app_time", "embed_data", "item"))
    assert body["mac"] == sign(config.ZALOPAY_KEY1, raw)


def test_create_rejects_wrong_owner_and_cash_order(ctx, monkeypatch):
    client, _ = ctx
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth(uid=2))
    assert r.status_code == 403
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, payment_method="CASH")))
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 400


def test_create_returns_502_when_zalopay_refuses(ctx):
    client, calls = ctx
    calls["create"] = {"return_code": 2, "sub_return_message": "Chữ ký không hợp lệ"}
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 502
    assert client.get("/api/payments/order/7", headers=auth()).json() == []


# ---------- Callback ----------
def test_callback_success_marks_paid_once(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    body = callback(txn)
    assert client.post("/api/payments/zalopay/callback", json=body).json()["return_code"] == 1
    assert client.post("/api/payments/zalopay/callback", json=body).json()["return_code"] == 2
    assert status_of(client) == "SUCCESS"
    assert calls["paid"] == [(7, "260000123")]


def test_callback_with_bad_mac_is_ignored(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    r = client.post("/api/payments/zalopay/callback", json=callback(txn, key="wrong"))
    assert r.json()["return_code"] == -1
    assert status_of(client) == "PENDING" and calls["paid"] == []


def test_callback_with_wrong_amount_is_ignored(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    r = client.post("/api/payments/zalopay/callback", json=callback(txn, amount=1000))
    assert r.json()["return_code"] == -1
    assert status_of(client) == "PENDING" and calls["paid"] == []


def test_callback_retry_when_order_service_down(ctx, monkeypatch):
    client, _ = ctx
    txn = create(client)["txn_ref"]

    def down(*a):
        raise order_client.OrderServiceUnavailable("down")

    monkeypatch.setattr(order_client, "mark_paid", down)
    r = client.post("/api/payments/zalopay/callback", json=callback(txn))
    assert r.json()["return_code"] == 0  # ZaloPay sẽ gửi lại
    assert status_of(client) == "PENDING"


# ---------- Khách quay về web ----------
def test_return_queries_zalopay_when_callback_not_arrived(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    calls["query"] = {"return_code": 1, "amount": 45000, "zp_trans_id": 260000999}
    r = client.get("/api/payments/zalopay/return", params=redirect(txn))
    assert r.status_code == 200
    assert r.json()["success"] is True and r.json()["order_id"] == 7
    assert calls["paid"] == [(7, "260000999")]
    url, body = calls["zalopay"][-1]
    assert url.endswith("/v2/query") and body["app_trans_id"] == txn
    assert body["mac"] == sign(config.ZALOPAY_KEY1, f"{config.ZALOPAY_APP_ID}|{txn}|{config.ZALOPAY_KEY1}")


def test_return_while_still_processing_stays_pending(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    r = client.get("/api/payments/zalopay/return", params=redirect(txn))
    assert r.json()["payment_status"] == "PENDING" and calls["paid"] == []


def test_return_rejects_tampered_query(ctx):
    client, _ = ctx
    txn = create(client)["txn_ref"]
    params = redirect(txn, status="-49")
    params["status"] = "1"  # khách tự sửa URL thành "thành công"
    assert client.get("/api/payments/zalopay/return", params=params).status_code == 400


def test_failed_then_late_callback_still_records_payment(ctx):
    client, calls = ctx
    txn = create(client)["txn_ref"]
    calls["query"] = {"return_code": 2, "sub_return_message": "Giao dịch thất bại"}
    r = client.get("/api/payments/zalopay/return", params=redirect(txn, status="-49"))
    assert r.json()["payment_status"] == "FAILED"
    # Khách quay lại app ZaloPay trả xong: tiền về thì vẫn phải ghi nhận
    assert client.post("/api/payments/zalopay/callback", json=callback(txn)).json()["return_code"] == 1
    assert status_of(client) == "SUCCESS"


# ---------- order-service hỏi đơn đã trả chưa ----------
def test_paid_check_with_sync_queries_pending_payments(ctx):
    client, calls = ctx
    create(client)
    r = client.get("/internal/payments/order/7/paid", headers=IK)
    assert r.json() == {"paid": False, "method": None}
    assert not any(u.endswith("/v2/query") for u, _ in calls["zalopay"])  # không sync thì không hỏi

    # Khách vừa quét mã xong nhưng callback chưa tới
    calls["query"] = {"return_code": 1, "amount": 45000, "zp_trans_id": 260000555}
    r = client.get("/internal/payments/order/7/paid", params={"sync": "true"}, headers=IK)
    assert r.json() == {"paid": True, "method": "ZALOPAY"}
    assert calls["paid"] == [(7, "260000555")]


def test_paid_check_requires_internal_key(ctx):
    client, _ = ctx
    assert client.get("/internal/payments/order/7/paid").status_code == 403


# ---------- Tiền mặt ----------
def test_cash_confirm_is_idempotent(ctx, monkeypatch):
    client, _ = ctx
    monkeypatch.setattr(order_client, "get_order",
                        lambda oid: (200, dict(ORDER, payment_method="CASH", status="READY")))
    staff = auth(uid=20, role="ADMIN")
    first = client.post("/api/payments/cash/confirm", json={"order_id": 7}, headers=staff)
    again = client.post("/api/payments/cash/confirm", json={"order_id": 7}, headers=staff)
    assert first.status_code == again.status_code == 200
    assert first.json()["id"] == again.json()["id"] and first.json()["method"] == "CASH"


def test_cash_at_station1_sends_order_to_kitchen(ctx, monkeypatch):
    client, calls = ctx
    monkeypatch.setattr(order_client, "get_order",
                        lambda oid: (200, dict(ORDER, payment_method="CASH", status="AWAITING_PAYMENT")))
    other = client.post("/api/payments/cash/confirm", json={"order_id": 7},
                        headers=auth(uid=21, role="STAFF", station=2))
    assert other.status_code == 403                          # nhân viên chi nhánh khác
    r = client.post("/api/payments/cash/confirm", json={"order_id": 7},
                    headers=auth(uid=20, role="STAFF", station=1))
    assert r.status_code == 200 and r.json()["status"] == "SUCCESS"
    assert calls["paid"] == [(7, "CASH7")] and calls["paid_method"] == ["CASH"]


def test_cannot_pay_before_station1(ctx, monkeypatch):
    """Đơn đang treo (chưa tới trạm 1): chưa tạo được giao dịch ZaloPay, chưa thu tiền mặt."""
    client, _ = ctx
    monkeypatch.setattr(order_client, "get_order", lambda oid: (200, dict(ORDER, status="HOLD")))
    r = client.post("/api/payments/zalopay/create", json={"order_id": 7}, headers=auth())
    assert r.status_code == 409 and "trạm 1" in r.json()["detail"]
    monkeypatch.setattr(order_client, "get_order",
                        lambda oid: (200, dict(ORDER, payment_method="CASH", status="HOLD")))
    r = client.post("/api/payments/cash/confirm", json={"order_id": 7}, headers=auth(uid=20, role="ADMIN"))
    assert r.status_code == 409
