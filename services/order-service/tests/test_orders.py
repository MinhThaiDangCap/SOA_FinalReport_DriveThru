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


# ---------- Tiện ích ----------
from datetime import datetime, timedelta, timezone

from app import payment_client
from app.estimate import order_prep_minutes


def minutes_from_now(iso: str) -> float:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - datetime.now(timezone.utc)).total_seconds() / 60


BODY = {"station_id": 1, "license_plate": "51a-12345", "contact_phone": "0901234567",
        "items": [{"menu_item_id": 1, "quantity": 2}]}
IK = {"X-Internal-Key": "ik"}
CUSTOMER = auth(10, "CUSTOMER")
STAFF1 = auth(20, "STAFF", 1)
KITCHEN1 = auth(30, "KITCHEN", 1)


def place(client, body=None, headers=CUSTOMER):
    r = client.post("/api/orders", json=body or BODY, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def check_in(client, oid, method="CASH", headers=STAFF1):
    return client.post(f"/api/orders/{oid}/check-in", json={"payment_method": method}, headers=headers)


def paid(client, oid, method="CASH", ref="1"):
    return client.post(f"/internal/orders/{oid}/payment-confirmed",
                       json={"transaction_ref": ref, "method": method}, headers=IK)


def in_kitchen(client, body=None, headers=CUSTOMER, method="CASH"):
    """Đơn đã qua trạm 1 và đã trả tiền: đang chờ bếp."""
    oid = place(client, body, headers)["id"]
    assert check_in(client, oid, method).status_code == 200
    assert paid(client, oid, method).json()["status"] == "CONFIRMED"
    return oid


def set_status(client, oid, status, headers):
    return client.patch(f"/api/orders/{oid}/status", json={"status": status}, headers=headers)


# ---------- Đặt trước: mã đơn, giữ đơn, chưa trả tiền ----------
def test_place_order_gets_pickup_code_and_hold(client):
    o = place(client)
    assert o["status"] == "HOLD" and o["payment_method"] is None
    assert len(o["pickup_code"]) == 4 and o["pickup_code"].isdigit()
    assert o["total_amount"] == 90000                       # 2 x 45000, giá lấy từ menu
    assert o["contact_phone"] == "0901234567"
    assert o["estimated_ready_at"] is None                  # bếp chưa thấy đơn treo
    # Hẹn tới trong 30 phút (mặc định), giữ thêm 10 phút
    assert 29.9 < minutes_from_now(o["expected_arrival_at"]) <= 30
    assert 39.9 < minutes_from_now(o["hold_expires_at"]) <= 40
    assert o["is_overdue"] is False


def test_place_order_validation(client):
    assert client.post("/api/orders", json={**BODY, "contact_phone": ""}, headers=CUSTOMER).status_code == 422
    assert client.post("/api/orders", json={**BODY, "arrival_minutes": 60}, headers=CUSTOMER).status_code == 422
    r = client.post("/api/orders", json={**BODY, "items": [{"menu_item_id": 4, "quantity": 1}]},
                    headers=CUSTOMER)
    assert r.status_code == 400                             # món đã hết
    assert client.post("/api/orders", json=BODY, headers=STAFF1).status_code == 403


def test_pickup_codes_unique_per_station_and_day(client):
    codes = {place(client)["pickup_code"] for _ in range(30)}
    assert len(codes) == 30


def test_customer_cannot_see_other_customers_order(client):
    oid = place(client)["id"]
    assert client.get(f"/api/orders/{oid}", headers=auth(11, "CUSTOMER")).status_code == 403


# ---------- Trạm 1: tìm đơn, nhận đơn, sửa biển số ----------
def test_station1_lookup_by_code_or_plate(client):
    o = place(client)
    by_code = client.get("/api/orders/station/lookup", params={"q": o["pickup_code"]}, headers=STAFF1)
    assert [x["id"] for x in by_code.json()] == [o["id"]]
    by_plate = client.get("/api/orders/station/lookup", params={"q": "51A-123.45"}, headers=STAFF1)
    assert o["id"] in [x["id"] for x in by_plate.json()]
    # Nhân viên chi nhánh khác không thấy
    other = client.get("/api/orders/station/lookup", params={"q": o["pickup_code"]},
                       headers=auth(21, "STAFF", 2))
    assert other.json() == []
    holds = client.get("/api/orders/station/holds", headers=STAFF1).json()
    assert [x["id"] for x in holds] == [o["id"]]


def test_check_in_cash_then_paid_goes_to_kitchen(client):
    oid = place(client)["id"]
    r = check_in(client, oid, "CASH")
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["payment_method"]) == ("AWAITING_PAYMENT", "CASH")
    assert r.json()["checked_in_at"] is not None

    done = paid(client, oid, "CASH")
    assert done.status_code == 200 and done.json()["status"] == "CONFIRMED"
    order = client.get(f"/api/orders/{oid}", headers=CUSTOMER).json()
    assert order["confirmed_at"] is not None and order["estimated_ready_at"] is not None
    assert order["history"][-1]["note"] == "Đã thanh toán tiền mặt, đơn vào bếp"


def test_check_in_rules(client):
    oid = place(client)["id"]
    assert check_in(client, oid, headers=auth(21, "STAFF", 2)).status_code == 403   # chi nhánh khác
    assert check_in(client, oid, headers=KITCHEN1).status_code == 403               # bếp không nhận đơn
    assert check_in(client, oid, headers=CUSTOMER).status_code == 403
    assert check_in(client, oid, "ZALOPAY").status_code == 200
    r = check_in(client, oid, "CASH")                        # ZaloPay lỗi, đổi sang tiền mặt
    assert r.status_code == 200 and r.json()["payment_method"] == "CASH"
    assert r.json()["history"][-1]["note"] == "Đổi sang trả tiền mặt"
    paid(client, oid, "CASH")
    assert check_in(client, oid).status_code == 409          # đã vào bếp


def test_paid_before_check_in_is_rejected(client):
    oid = place(client)["id"]
    assert paid(client, oid).status_code == 409


def test_late_zalopay_after_switching_to_cash_records_zalopay(client):
    oid = place(client)["id"]
    check_in(client, oid, "ZALOPAY")
    check_in(client, oid, "CASH")                            # nhân viên đổi sang tiền mặt
    paid(client, oid, "ZALOPAY", ref="260000123")            # nhưng khách kịp trả ZaloPay
    order = client.get(f"/api/orders/{oid}", headers=CUSTOMER).json()
    assert (order["status"], order["payment_method"]) == ("CONFIRMED", "ZALOPAY")
    assert order["history"][-1]["note"] == "Đã thanh toán ZaloPay, đơn vào bếp (mã GD: 260000123)"


def test_update_plate(client):
    oid = place(client)["id"]
    r = client.patch(f"/api/orders/{oid}/plate", json={"license_plate": "59x1-123.45"}, headers=CUSTOMER)
    assert r.status_code == 200 and r.json()["license_plate"] == "59X1-123.45"
    assert r.json()["history"][-1]["note"] == "Sửa biển số 51A-12345 -> 59X1-123.45"
    assert client.patch(f"/api/orders/{oid}/plate", json={"license_plate": "51A-99999"},
                        headers=auth(11, "CUSTOMER")).status_code == 403
    check_in(client, oid)
    # Khách không sửa nữa khi đã ở trạm 1; nhân viên xác minh rồi sửa được
    assert client.patch(f"/api/orders/{oid}/plate", json={"license_plate": "51A-99999"},
                        headers=CUSTOMER).status_code == 409
    assert client.patch(f"/api/orders/{oid}/plate", json={"license_plate": "51A-99999"},
                        headers=STAFF1).status_code == 200


# ---------- Hủy: chỉ đơn chưa trả tiền, hệ thống không tự hủy ----------
def test_customer_and_station_staff_cancel_unpaid_orders(client):
    oid = place(client)["id"]
    r = client.post(f"/api/orders/{oid}/cancel", headers=CUSTOMER)
    assert r.status_code == 200 and r.json()["history"][-1]["note"] == "Khách hủy đơn"

    oid = place(client)["id"]
    assert client.post(f"/api/orders/{oid}/cancel", headers=auth(11, "CUSTOMER")).status_code == 403
    assert client.post(f"/api/orders/{oid}/cancel", headers=auth(21, "STAFF", 2)).status_code == 403
    assert client.post(f"/api/orders/{oid}/cancel", headers=KITCHEN1).status_code == 403
    r = client.post(f"/api/orders/{oid}/cancel", headers=STAFF1)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert client.post(f"/api/orders/{oid}/cancel", headers=STAFF1).status_code == 409


def test_overdue_hold_is_flagged_not_cancelled(client):
    from app.database import get_db
    from app.models import Order

    oid = place(client)["id"]
    db = next(app.dependency_overrides[get_db]())
    order = db.get(Order, oid)
    order.hold_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    db.close()

    holds = client.get("/api/orders/station/holds", headers=STAFF1).json()
    assert holds[0]["id"] == oid and holds[0]["is_overdue"] is True
    assert holds[0]["status"] == "HOLD"                       # chưa bị hủy
    r = client.post(f"/api/orders/{oid}/cancel", headers=STAFF1)
    assert r.json()["history"][-1]["note"] == "Nhân viên trạm 1 hủy đơn quá hạn giữ"


def test_cannot_cancel_after_payment(client):
    oid = in_kitchen(client)
    r = client.post(f"/api/orders/{oid}/cancel", headers=CUSTOMER)
    assert r.status_code == 409 and "không thể hủy" in r.json()["detail"]


def test_cancel_awaiting_zalopay_checks_payment_first(client, monkeypatch):
    calls = []
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: calls.append(sync) or False)
    oid = place(client)["id"]
    check_in(client, oid, "ZALOPAY")
    r = client.post(f"/api/orders/{oid}/cancel", headers=CUSTOMER)
    assert r.status_code == 200 and calls == [True]          # đã hỏi ZaloPay trước khi hủy


def test_cancel_blocked_when_customer_just_paid(client, monkeypatch):
    """Khách vừa trả ZaloPay xong, callback chưa tới: tra cứu thấy đã trả thì không hủy."""
    oid = place(client)["id"]
    check_in(client, oid, "ZALOPAY")

    def just_paid(order_id, sync=False):
        paid(client, order_id, "ZALOPAY", ref="9")
        return True

    monkeypatch.setattr(payment_client, "is_paid", just_paid)
    r = client.post(f"/api/orders/{oid}/cancel", headers=CUSTOMER)
    assert r.status_code == 409


def test_cancel_hold_does_not_ask_payment(client, monkeypatch):
    monkeypatch.setattr(payment_client, "is_paid", lambda oid, sync=False: pytest.fail("không được gọi"))
    oid = place(client)["id"]
    assert client.post(f"/api/orders/{oid}/cancel", headers=CUSTOMER).status_code == 200


# ---------- Bếp và trạm 2: ai làm bước nào ----------
def test_kitchen_and_station2_roles(client):
    oid = in_kitchen(client)
    # Nhân viên trạm không làm việc của bếp, bếp không giao món
    assert set_status(client, oid, "PREPARING", STAFF1).status_code == 403
    assert set_status(client, oid, "PREPARING", auth(31, "KITCHEN", 2)).status_code == 403
    assert set_status(client, oid, "COMPLETED", KITCHEN1).status_code == 403
    assert set_status(client, oid, "READY", KITCHEN1).status_code == 409   # phải bắt đầu làm trước
    assert set_status(client, oid, "PREPARING", KITCHEN1).status_code == 200
    assert set_status(client, oid, "READY", KITCHEN1).status_code == 200

    ready = client.get("/api/orders/station/ready", headers=STAFF1).json()
    assert [o["id"] for o in ready] == [oid]
    r = set_status(client, oid, "COMPLETED", STAFF1)
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"


def test_kitchen_sees_only_paid_orders_of_own_station(client):
    place(client)                                             # đơn treo: bếp không thấy
    oid = in_kitchen(client)
    assert [o["id"] for o in client.get("/api/orders/kitchen", headers=KITCHEN1).json()] == [oid]
    assert client.get("/api/orders/kitchen", headers=auth(31, "KITCHEN", 2)).json() == []
    assert client.get("/api/orders/kitchen", headers=STAFF1).status_code == 403
    assert client.get(f"/api/orders/{oid}", headers=KITCHEN1).status_code == 200      # in phiếu
    assert client.get(f"/api/orders/{oid}", headers=auth(31, "KITCHEN", 2)).status_code == 403
    assert client.get("/api/orders/station/holds", headers=KITCHEN1).status_code == 403


# ---------- Hàng đợi bếp: đơn nhanh trước, đơn chờ lâu được đẩy lên ----------
BURGER = {"menu_item_id": 1, "quantity": 1}   # 5 phút
DRINK = {"menu_item_id": 3, "quantity": 1}    # 2 phút


def test_kitchen_queue_short_orders_first(client):
    long_ = in_kitchen(client, {**BODY, "items": [{"menu_item_id": 1, "quantity": 6}]})   # 5 + 2 = 7'
    mid = in_kitchen(client, {**BODY, "items": [BURGER]})                                 # 5'
    short = in_kitchen(client, {**BODY, "items": [DRINK]})                                # 2'
    queue = client.get("/api/orders/kitchen", headers=KITCHEN1).json()
    assert [o["id"] for o in queue] == [short, mid, long_]

    # Giờ dự kiến theo đúng thứ tự: bếp làm 2 đơn cùng lúc
    eta = {o["id"]: minutes_from_now(o["estimated_ready_at"]) for o in queue}
    assert 1.9 < eta[short] <= 2 and 4.9 < eta[mid] <= 5
    assert 8.9 < eta[long_] <= 9                              # chờ chỗ trống sau đơn 2' rồi làm 7'


def test_long_waiting_order_is_pushed_to_front(client):
    from app.database import get_db
    from app.models import Order

    long_ = in_kitchen(client, {**BODY, "items": [{"menu_item_id": 1, "quantity": 6}]})
    short = in_kitchen(client, {**BODY, "items": [DRINK]})
    db = next(app.dependency_overrides[get_db]())
    db.get(Order, long_).confirmed_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    db.commit()
    db.close()
    queue = client.get("/api/orders/kitchen", headers=KITCHEN1).json()
    assert [o["id"] for o in queue] == [long_, short]         # chờ quá 10 phút: lên đầu


def test_preparing_order_keeps_slot_and_resets_estimate(client):
    first = in_kitchen(client)
    second = in_kitchen(client)
    r = set_status(client, second, "PREPARING", KITCHEN1)
    # bếp bắt đầu làm đơn này: xong sau đúng 5 phút
    assert 4.9 < minutes_from_now(r.json()["estimated_ready_at"]) <= 5
    queue = client.get("/api/orders/kitchen", headers=KITCHEN1).json()
    assert [o["id"] for o in queue] == [second, first]        # đơn đang làm đứng đầu


def test_order_prep_minutes_formula():
    assert order_prep_minutes([]) == 0
    assert order_prep_minutes([(5, 1)]) == 5              # 1 burger
    assert order_prep_minutes([(5, 2)]) == 5              # thêm 1 phần: chưa cộng
    assert order_prep_minutes([(5, 2), (2, 3)]) == 7      # món lâu nhất 5 + 4 phần thêm / 2


def test_wait_times_public(client):
    for _ in range(3):
        in_kitchen(client)
    place(client)                                         # đơn treo không tính
    r = client.get("/api/orders/wait-times")              # không cần token
    assert r.status_code == 200
    # 3 đơn x 5 phút, bếp làm 2 đơn cùng lúc: 2 đơn đầu xong ở phút 5, đơn thứ 3 ở phút 10,
    # nên đơn mới có chỗ sau 5 phút, + 5 phút cho một đơn điển hình
    assert r.json() == [{"station_id": 1, "queue_count": 3, "estimated_minutes": 10}]


def test_admin_stats_and_recent(client):
    oid = in_kitchen(client)
    for s, h in (("PREPARING", KITCHEN1), ("READY", KITCHEN1), ("COMPLETED", STAFF1)):
        assert set_status(client, oid, s, h).status_code == 200
    place(client)                                         # 1 đơn đang treo

    assert client.get("/api/orders/stats", headers=STAFF1).status_code == 403
    stats = client.get("/api/orders/stats", headers=auth(1, "ADMIN")).json()
    assert stats == [{"station_id": 1, "total_orders": 2, "active_orders": 1, "completed_orders": 1,
                      "cancelled_orders": 0, "revenue": 90000, "today_orders": stats[0]["today_orders"],
                      "today_revenue": stats[0]["today_revenue"]}]

    recent = client.get("/api/orders/recent", headers=STAFF1).json()
    assert [o["id"] for o in recent] == [oid]
    assert client.get("/api/orders/recent", headers=auth(20, "STAFF", 2)).json() == []


# ---------- Quyền tạo mã giảm giá ----------
def test_only_admin_creates_coupon(client):
    body = {"code": "TEST10", "discount_type": "PERCENT", "discount_value": 10,
            "valid_from": "2026-01-01", "valid_to": "2026-12-31"}
    assert client.post("/api/orders/coupons", json=body).status_code == 401
    assert client.post("/api/orders/coupons", json=body, headers=CUSTOMER).status_code == 403
    assert client.post("/api/orders/coupons", json=body, headers=STAFF1).status_code == 403
    assert client.post("/api/orders/coupons", json=body, headers=KITCHEN1).status_code == 403
    assert client.post("/api/orders/coupons", json=body, headers=auth(1, "ADMIN")).status_code == 201


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
