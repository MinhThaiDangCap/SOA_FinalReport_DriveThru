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