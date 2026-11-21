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

# ---------- Hủy đơn ZaloPay: đã trả thì không cho tự hủy, khách gọi hotline ----------
from app import payment_client

ZP = {**BODY, "payment_method": "ZALOPAY"}


def paid_zalopay_order(client):
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]
    r = client.post(f"/internal/orders/{oid}/payment-confirmed",
                    json={"transaction_ref": "123"}, headers={"X-Internal-Key": "ik"})
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"
    return oid


def test_cannot_cancel_paid_zalopay_order(client):
    oid = paid_zalopay_order(client)
    r = client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 409 and "hotline" in r.json()["detail"]
    assert client.get(f"/api/orders/{oid}", headers=auth(10, "CUSTOMER")).json()["status"] == "CONFIRMED"


def test_cancel_unpaid_zalopay_checks_payment_first(client, monkeypatch):
    calls = []
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: calls.append(sync) or False)
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]
    r = client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert calls == [True]  # đã hỏi ZaloPay trước khi hủy


def test_cancel_blocked_when_customer_just_paid(client, monkeypatch):
    """Khách vừa quét mã xong, callback chưa tới: tra cứu thấy đã trả thì không cho hủy."""
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]

    def just_paid(order_id, sync=False):
        # payment-service tra cứu ZaloPay thấy đã trả -> gọi lại order-service xác nhận đơn
        client.post(f"/internal/orders/{order_id}/payment-confirmed",
                    json={"transaction_ref": "9"}, headers={"X-Internal-Key": "ik"})
        return True

    monkeypatch.setattr(payment_client, "is_paid", just_paid)
    r = client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 409 and "hotline" in r.json()["detail"]


def test_cancel_cash_order_does_not_ask_payment(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: pytest.fail("không được gọi"))
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
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
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: paid["v"])
    oid = ready_cash_order(client)
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"}, headers=auth(20, "STAFF", 1))
    assert r.status_code == 409 and "thu tiền" in r.json()["detail"]
    paid["v"] = True
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "COMPLETED"}, headers=auth(20, "STAFF", 1))
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"


def test_admin_stats_and_recent(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: True)
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


def test_wait_times_public(client):
    for _ in range(3):
        client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER"))
    r = client.get("/api/orders/wait-times")  # không cần token
    assert r.status_code == 200
    # Mỗi đơn 2 burger = 5 phút; 3 đơn = 15 phút, bếp làm 2 đơn cùng lúc -> chờ 8 phút
    # + 5 phút cho một đơn điển hình
    assert r.json() == [{"station_id": 1, "queue_count": 3, "estimated_minutes": 13}]


# ---------- Đổi phương thức thanh toán ----------
def change_method(client, oid, method, uid=10):
    return client.patch(f"/api/orders/{oid}/payment-method", json={"payment_method": method},
                        headers=auth(uid, "CUSTOMER"))


def test_switch_unpaid_zalopay_to_cash(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: False)
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]

    assert change_method(client, oid, "CASH", uid=11).status_code == 403  # đơn người khác
    r = change_method(client, oid, "CASH")
    assert r.status_code == 200
    assert (r.json()["payment_method"], r.json()["status"]) == ("CASH", "CONFIRMED")
    assert r.json()["history"][-1]["note"] == "Khách đổi sang trả tại quầy"
    assert r.json()["estimated_ready_at"] is not None          # đã vào hàng đợi của bếp
    assert change_method(client, oid, "CASH").status_code == 200  # giữ nguyên, không lỗi


def test_cash_order_cannot_switch_to_zalopay(client, monkeypatch):
    """Đơn trả tại quầy đã nằm trong hàng đợi: không rút về chờ thanh toán."""
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: False)
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    r = change_method(client, oid, "ZALOPAY")
    assert r.status_code == 409 and "hủy đơn" in r.json()["detail"]

    order = client.get(f"/api/orders/{oid}", headers=auth(10, "CUSTOMER")).json()
    assert (order["payment_method"], order["status"]) == ("CASH", "CONFIRMED")
    queue = client.get("/api/orders/queue", headers=auth(20, "STAFF", 1)).json()
    assert any(o["id"] == oid for o in queue)                   # quầy vẫn thấy đơn


def test_cannot_switch_after_paid(client, monkeypatch):
    oid = paid_zalopay_order(client)  # ZaloPay đã trả -> CONFIRMED
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: False)
    assert change_method(client, oid, "CASH").status_code == 409

    # Khách vừa quét mã xong nhưng đơn chưa kịp cập nhật
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: True)
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]
    assert change_method(client, oid, "CASH").status_code == 409


def test_late_zalopay_payment_after_switching_to_cash(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: False)
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]
    change_method(client, oid, "CASH")
    r = client.post(f"/internal/orders/{oid}/payment-confirmed",
                    json={"transaction_ref": "1"}, headers={"X-Internal-Key": "ik"})
    assert r.status_code == 200
    order = client.get(f"/api/orders/{oid}", headers=auth(10, "CUSTOMER")).json()
    assert (order["payment_method"], order["status"]) == ("ZALOPAY", "CONFIRMED")
    assert order["history"][-1]["note"] == "Khách đã thanh toán ZaloPay, không cần thu tiền mặt"


# ---------- Khách tới sớm: chỉ ghi giờ đến, không nhảy qua bước bếp ----------
STAFF1 = auth(20, "STAFF", 1)


def set_status(client, oid, status):
    return client.patch(f"/api/orders/{oid}/status", json={"status": status}, headers=STAFF1)


def test_early_arrival_keeps_kitchen_status(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: True)
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    set_status(client, oid, "PREPARING")

    r = client.post(f"/api/orders/{oid}/arrived", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 200
    assert r.json()["status"] == "PREPARING" and r.json()["arrived_at"] is not None
    assert r.json()["history"][-1]["note"] == "Khách báo đã tới quầy"

    # Bấm lại: không lỗi, không ghi thêm lịch sử
    again = client.post(f"/api/orders/{oid}/arrived", headers=auth(10, "CUSTOMER")).json()
    assert len(again["history"]) == len(r.json()["history"])

    # Món chưa xong thì không giao được, phải qua READY
    assert set_status(client, oid, "COMPLETED").status_code == 409
    assert set_status(client, oid, "READY").status_code == 200
    assert set_status(client, oid, "COMPLETED").status_code == 200


def test_arrival_rules(client):
    oid = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()["id"]
    r = client.post(f"/api/orders/{oid}/arrived", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 409 and "chưa được thanh toán" in r.json()["detail"]

    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    assert client.post(f"/api/orders/{oid}/arrived", headers=auth(11, "CUSTOMER")).status_code == 403
    r = client.post(f"/api/orders/{oid}/arrived", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"  # tới trước khi bếp làm


def test_cannot_cancel_once_store_started(client):
    oid = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()["id"]
    client.patch(f"/api/orders/{oid}/status", json={"status": "PREPARING"}, headers=auth(20, "STAFF", 1))
    r = client.post(f"/api/orders/{oid}/cancel", headers=auth(10, "CUSTOMER"))
    assert r.status_code == 409
    assert r.json()["detail"] == "Cửa hàng đã bắt đầu làm món nên không thể hủy đơn nữa."


# ---------- Ước lượng giờ xong đơn ----------
from datetime import datetime, timezone

from app.estimate import order_prep_minutes


def minutes_from_now(iso: str) -> float:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - datetime.now(timezone.utc)).total_seconds() / 60


def test_order_prep_minutes_formula():
    assert order_prep_minutes([]) == 0
    assert order_prep_minutes([(5, 1)]) == 5              # 1 burger
    assert order_prep_minutes([(5, 2)]) == 5              # thêm 1 phần: chưa cộng
    assert order_prep_minutes([(5, 2), (2, 3)]) == 7      # món lâu nhất 5 + 4 phần thêm / 2


def test_estimate_counts_orders_ahead(client):
    first = client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER")).json()
    assert first["prep_minutes"] == 5
    assert first["items"][0]["prep_minutes"] == 5
    assert 4.9 < minutes_from_now(first["estimated_ready_at"]) <= 5      # bếp đang trống

    second = client.post("/api/orders", json=BODY, headers=auth(11, "CUSTOMER")).json()
    # chờ đơn trước: 5 phút / 2 đơn cùng lúc = 3 phút (làm tròn lên), cộng 5 phút làm
    assert 7.9 < minutes_from_now(second["estimated_ready_at"]) <= 8


def test_zalopay_estimate_set_only_after_payment(client):
    created = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER")).json()
    assert created["estimated_ready_at"] is None                         # chưa trả tiền

    paid = client.post(f"/internal/orders/{created['id']}/payment-confirmed",
                       json={"transaction_ref": "1"}, headers={"X-Internal-Key": "ik"})
    assert paid.json()["status"] == "CONFIRMED"
    order = client.get(f"/api/orders/{created['id']}", headers=auth(10, "CUSTOMER")).json()
    assert 4.9 < minutes_from_now(order["estimated_ready_at"]) <= 5


def test_estimate_resets_when_kitchen_starts(client):
    client.post("/api/orders", json=BODY, headers=auth(10, "CUSTOMER"))
    oid = client.post("/api/orders", json=BODY, headers=auth(11, "CUSTOMER")).json()["id"]
    r = client.patch(f"/api/orders/{oid}/status", json={"status": "PREPARING"},
                     headers=auth(20, "STAFF", 1))
    # bếp bắt đầu làm đơn này: không còn phải chờ đơn trước, xong sau 5 phút
    assert 4.9 < minutes_from_now(r.json()["estimated_ready_at"]) <= 5


def test_zalopay_order_waits_for_payment(client):
    r = client.post("/api/orders", json=ZP, headers=auth(10, "CUSTOMER"))
    assert r.status_code == 201
    assert r.json()["status"] == "PENDING_PAYMENT"
    assert r.json()["history"][-1]["note"] == "Chờ thanh toán ZaloPay"
    paid = client.post(f"/internal/orders/{r.json()['id']}/payment-confirmed",
                       json={"transaction_ref": "260000123"}, headers={"X-Internal-Key": "ik"})
    assert paid.json()["status"] == "CONFIRMED"
    order = client.get(f"/api/orders/{r.json()['id']}", headers=auth(10, "CUSTOMER")).json()
    assert order["history"][-1]["note"] == "Thanh toán ZaloPay thành công (mã GD: 260000123)"


# ---------- Mã giảm giá: khách chọn từ danh sách ----------
def test_available_coupons_for_customer(client):
    from datetime import date, timedelta

    admin = auth(1, "ADMIN")
    today = date.today()
    for code, kind, value, start, end, active in (
        ("GIAM10", "PERCENT", 10, today, today + timedelta(days=5), True),
        ("BOT20K", "FIXED", 20000, today, today, True),
        ("HETHAN", "FIXED", 5000, today - timedelta(days=9), today - timedelta(days=1), True),
        ("TATMA", "FIXED", 5000, today, today, False),
    ):
        r = client.post("/api/orders/coupons", headers=admin, json={
            "code": code, "discount_type": kind, "discount_value": value,
            "valid_from": str(start), "valid_to": str(end), "is_active": active})
        assert r.status_code == 201, r.text

    assert client.get("/api/orders/coupons/available", params={"subtotal": 90000}).status_code == 401
    r = client.get("/api/orders/coupons/available", params={"subtotal": 90000},
                   headers=auth(10, "CUSTOMER"))
    assert r.status_code == 200
    # Chỉ mã đang bật và còn hạn, giảm nhiều nhất xếp trước
    assert [(c["code"], c["discount_amount"]) for c in r.json()] == [("BOT20K", 20000), ("GIAM10", 9000)]
    # Giảm không vượt quá tiền hàng
    r = client.get("/api/orders/coupons/available", params={"subtotal": 15000},
                   headers=auth(10, "CUSTOMER"))
    assert r.json()[0] == {**r.json()[0], "code": "BOT20K", "discount_amount": 15000}
