import os, time
os.environ.update(MENU_MOCK="true", JWT_SECRET="test", INTERNAL_KEY="ik")

import jwt, pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


@pytest.fixture()
def client():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)  # không dùng "with" để khỏi chạy lifespan (kết nối Postgres)
    app.dependency_overrides.clear()


def auth(uid, role, station=None):
    p = {"sub": str(uid), "role": role, "exp": int(time.time()) + 3600}
    if station:
        p["station_id"] = station
    return {"Authorization": "Bearer " + jwt.encode(p, "test", algorithm="HS256")}


BODY = {"station_id": 1, "license_plate": "51a-12345", "payment_method": "CASH",
        "items": [{"menu_item_id": 1, "quantity": 2}]}


def test_create_order_computes_price_server_side(client):
    r = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER"))
    assert r.status_code == 201
    assert r.json()["total_amount"] == 90000          # 2 x 45000, giá lấy từ menu
    assert r.json()["status"] == "CONFIRMED"


def test_out_of_stock_item_rejected(client):
    body = {**BODY, "items": [{"menu_item_id": 4, "quantity": 1}]}
    r = client.post("/api/orders", json=body, headers=auth(10, "CUSTOMER"))
    assert r.status_code == 400


def test_invalid_transition_returns_409(client):
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"},
                     headers=auth(20, "STAFF", 1))
    assert r.status_code == 409                       # CONFIRMED không nhảy thẳng COMPLETED


def test_customer_cannot_see_other_customers_order(client):
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    assert client.get(f"/api/orders/{oid}", headers=auth(11, "CUSTOMER")).status_code == 403

# ---------- Hủy đơn MoMo đã trả: phải hoàn tiền trước ----------
from fastapi import HTTPException
from app import payment_client


def paid_momo_order(client):
    body = {**BODY, "payment_method": "MOMO"}
    oid = client.post("/api/orders", json=body, headers=auth(10, "CUSTOMER")).json()["id"]
    r = client.post(f"/internal/orders/{oid}/payment-confirmed",
                    json={"transaction_ref": "123"}, headers={"X-Internal-Key": "ik"})
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"
    return oid


def test_cancel_paid_momo_order_refunds_first(client, monkeypatch):
    calls = []
    monkeypatch.setattr(payment_client, "refund_order",
                        lambda oid: calls.append(oid) or {"refunded": True, "amount": 90000})
    oid = paid_momo_order(client)
    r = client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert calls == [oid]
    assert r.json()["history"][-1]["note"] == "Khách hủy đơn, đã hoàn 90.000đ về ví MoMo"


def test_cancel_kept_when_refund_fails(client, monkeypatch):
    def fail(oid):
        raise HTTPException(status_code=502, detail="MoMo chưa hoàn tiền được")
    monkeypatch.setattr(payment_client, "refund_order", fail)
    oid = paid_momo_order(client)
    assert client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER")).status_code == 502
    assert client.get(f"/api/orders/{oid}", headers=auth(10, "CUSTOMER")).json()["status"] == "CONFIRMED"


def test_cancel_unpaid_or_cash_order_skips_refund(client, monkeypatch):
    monkeypatch.setattr(payment_client, "refund_order", lambda oid: pytest.fail("không được gọi"))
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    assert client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER")).status_code == 200
    body = {**BODY, "payment_method": "MOMO"}
    oid = client.post("/api/orders", json=body, headers=auth(10, "CUSTOMER")).json()["id"]
    assert client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER")).status_code == 200


# ---------- Đơn tiền mặt: phải thu tiền rồi mới hoàn thành ----------
def ready_cash_order(client):
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    for s in ("PREPARING", "READY"):
        assert client.patch(f"/api/orders/{oid}/status", json={"status": s},
                            headers=auth(20, "STAFF", 1)).status_code == 200
    return oid


def test_cash_order_needs_payment_before_completed(client, monkeypatch):
    paid = {"v": False}
    monkeypatch.setattr(payment_client, "is_paid", lambda oid: paid["v"])
    oid = ready_cash_order(client)
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"}, headers=auth(20, "STAFF", 1))
    assert r.status_code == 409 and "thu tiền" in r.json()["detail"]
    paid["v"] = True
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"}, headers=auth(20, "STAFF", 1))
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"


def test_admin_stats_and_recent(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid: True)
    oid = ready_cash_order(client)
    client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"}, headers=auth(20, "STAFF", 1))
    client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER"))  # 1 đơn đang chờ

    assert client.get("/api/orders/stats", headers=auth(20, "STAFF", 1)).status_code == 403
    stats = client.get("/api/orders/stats", headers=auth(1, "ADMIN")).json()
    assert stats == [{"station_id": 1, "total_orders": 2, "active_orders": 1, "completed_orders": 1,
                      "cancelled_orders": 0, "revenue": 90000, "today_orders": stats[0]["today_orders"],
                      "today_revenue": stats[0]["today_revenue"]}]

    recent = client.get("/api/orders/recent", headers=auth(20, "STAFF", 1)).json()
    assert [o["id"] for o in recent] == [oid]
    assert client.get("/api/orders/recent", headers=auth(20, "STAFF", 2)).json() == []
