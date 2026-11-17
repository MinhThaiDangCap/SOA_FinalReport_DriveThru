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

    calls = {"momo": [], "paid": []}

    class FakeResp:
        def json(self):
            return {"resultCode": 0, "payUrl": "https://test-payment.momo.vn/pay/abc"}

    def fake_post(url, json, timeout):
        calls["momo"].append((url, json))
        return FakeResp()

    def fake_mark_paid(order_id, ref):
        calls["paid"].append((order_id, ref))
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
