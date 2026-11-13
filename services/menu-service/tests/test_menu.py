from conftest import ADMIN, CUSTOMER, INTERNAL, make_token


def availability_url(station_id: int, item_id: int) -> str:
    return f"/api/menu/stations/{station_id}/items/{item_id}/availability"


# ---------- Hệ thống ----------
def test_health_and_metrics(client):
    assert client.get("/health").json() == {"status": "ok", "service": "menu-service"}
    assert client.get("/metrics").status_code == 200


# ---------- Khách xem ----------
def test_customer_views_stations_and_menu_without_login(client, data):
    stations = client.get("/api/menu/stations").json()
    assert [s["name"] for s in stations] == ["Quận 7"]

    menu = client.get(f"/api/menu/stations/{data['station']['id']}/menu").json()
    assert menu["station"]["name"] == "Quận 7"
    assert len(menu["categories"]) == 1
    items = menu["categories"][0]["items"]
    assert [i["name"] for i in items] == ["Burger bò", "Burger gà"]
    assert all(i["available"] for i in items)


def test_menu_of_unknown_station_is_404(client):
    resp = client.get("/api/menu/stations/999/menu")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_empty_category_is_hidden_from_menu(client, data):
    client.post("/api/menu/categories", json={"name": "Đồ uống"}, headers=ADMIN)
    menu = client.get(f"/api/menu/stations/{data['station']['id']}/menu").json()
    assert [c["name"] for c in menu["categories"]] == ["Burger"]


# ---------- Phân quyền ----------
def test_write_endpoints_require_admin(client, data):
    body = {"name": "X", "address": "Y"}
    assert client.post("/api/menu/stations", json=body).status_code == 401
    assert client.post("/api/menu/stations", json=body, headers=CUSTOMER).status_code == 403
    staff = make_token("STAFF", station_id=1)
    assert client.post("/api/menu/categories", json={"name": "Z"}, headers=staff).status_code == 403


def test_invalid_token_is_rejected(client):
    resp = client.post(
        "/api/menu/categories",
        json={"name": "Z"},
        headers={"Authorization": "Bearer khong-phai-jwt"},
    )
    assert resp.status_code == 401


# ---------- Nhân viên báo còn / hết ----------
def test_staff_marks_item_sold_out_at_own_station(client, data):
    sid, item_id = data["station"]["id"], data["items"][0]["id"]
    staff = make_token("STAFF", user_id=5, station_id=sid)

    resp = client.put(availability_url(sid, item_id), json={"available": False}, headers=staff)
    assert resp.status_code == 200
    assert resp.json() == {"station_id": sid, "item_id": item_id, "available": False}

    items = client.get(f"/api/menu/stations/{sid}/menu").json()["categories"][0]["items"]
    assert {i["id"]: i["available"] for i in items} == {
        item_id: False,
        data["items"][1]["id"]: True,
    }

    # Báo có lại
    client.put(availability_url(sid, item_id), json={"available": True}, headers=staff)
    items = client.get(f"/api/menu/stations/{sid}/menu").json()["categories"][0]["items"]
    assert all(i["available"] for i in items)


def test_sold_out_only_affects_that_station(client, data):
    other = client.post(
        "/api/menu/stations", json={"name": "Thủ Đức", "address": "XLHN"}, headers=ADMIN
    ).json()
    sid, item_id = data["station"]["id"], data["items"][0]["id"]
    client.put(availability_url(sid, item_id), json={"available": False}, headers=ADMIN)

    items = client.get(f"/api/menu/stations/{other['id']}/menu").json()["categories"][0]["items"]
    assert all(i["available"] for i in items)


def test_staff_cannot_change_other_station(client, data):
    sid, item_id = data["station"]["id"], data["items"][0]["id"]
    staff_elsewhere = make_token("STAFF", station_id=sid + 1)
    resp = client.put(
        availability_url(sid, item_id), json={"available": False}, headers=staff_elsewhere
    )
    assert resp.status_code == 403


def test_customer_cannot_change_availability(client, data):
    sid, item_id = data["station"]["id"], data["items"][0]["id"]
    resp = client.put(availability_url(sid, item_id), json={"available": False}, headers=CUSTOMER)
    assert resp.status_code == 403


# ---------- Admin quản lý ----------
def test_admin_updates_and_deactivates_item(client, data):
    item = data["items"][0]
    resp = client.put(
        f"/api/menu/items/{item['id']}",
        json={"category_id": item["category_id"], "name": "Burger bò lớn", "price": 55000},
        headers=ADMIN,
    )
    assert resp.status_code == 200
    assert resp.json()["price"] == 55000

    assert client.delete(f"/api/menu/items/{item['id']}", headers=ADMIN).status_code == 204
    menu = client.get(f"/api/menu/stations/{data['station']['id']}/menu").json()
    assert [i["name"] for i in menu["categories"][0]["items"]] == ["Burger gà"]
    # Xóa mềm: vẫn tra được theo id
    assert client.get(f"/api/menu/items/{item['id']}").json()["is_active"] is False


def test_item_validation(client, data):
    cat = data["category"]["id"]
    bad_price = {"category_id": cat, "name": "Lỗi", "price": -1}
    assert client.post("/api/menu/items", json=bad_price, headers=ADMIN).status_code == 422
    bad_category = {"category_id": 999, "name": "Lỗi", "price": 1000}
    resp = client.post("/api/menu/items", json=bad_category, headers=ADMIN)
    assert resp.status_code == 400


def test_category_rules(client, data):
    cat = data["category"]["id"]
    dup = client.post("/api/menu/categories", json={"name": "burger"}, headers=ADMIN)
    assert dup.status_code == 409
    # Còn món thì không xóa được
    assert client.delete(f"/api/menu/categories/{cat}", headers=ADMIN).status_code == 409

    empty = client.post("/api/menu/categories", json={"name": "Trống"}, headers=ADMIN).json()
    assert client.delete(f"/api/menu/categories/{empty['id']}", headers=ADMIN).status_code == 204


def test_deactivated_station_disappears_for_customers(client, data):
    sid = data["station"]["id"]
    assert client.delete(f"/api/menu/stations/{sid}", headers=ADMIN).status_code == 204
    assert client.get("/api/menu/stations").json() == []
    assert client.get(f"/api/menu/stations/{sid}/menu").status_code == 404
    # Admin vẫn thấy
    assert len(client.get("/api/menu/stations/all", headers=ADMIN).json()) == 1


# ---------- Nội bộ (order-service gọi) ----------
def test_internal_items_requires_key(client, data):
    url = f"/internal/items?station_id={data['station']['id']}&ids=1"
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"X-Internal-Key": "sai"}).status_code == 403


def test_internal_items_contract_for_order_service(client, data):
    sid = data["station"]["id"]
    a, b = data["items"]
    client.put(availability_url(sid, b["id"]), json={"available": False}, headers=ADMIN)

    resp = client.get(
        f"/internal/items?station_id={sid}&ids={a['id']},{b['id']},999", headers=INTERNAL
    )
    assert resp.status_code == 200
    by_id = {i["id"]: i for i in resp.json()}
    # Món 999 không tồn tại nên không có trong kết quả
    assert by_id == {
        a["id"]: {"id": a["id"], "name": "Burger bò", "price": 45000, "available": True},
        b["id"]: {"id": b["id"], "name": "Burger gà", "price": 42000, "available": False},
    }


def test_internal_items_edge_cases(client, data):
    sid = data["station"]["id"]
    assert client.get("/internal/items?station_id=999&ids=1", headers=INTERNAL).json() == []
    bad = client.get(f"/internal/items?station_id={sid}&ids=a,b", headers=INTERNAL)
    assert bad.status_code == 400


def test_seed_matches_order_service_mock_ids(client):
    from app.database import SessionLocal
    from app.seed import seed_if_empty

    with SessionLocal() as db:
        assert seed_if_empty(db) is True
        assert seed_if_empty(db) is False  # không seed lần hai

    resp = client.get("/internal/items?station_id=1&ids=1,2,3,4", headers=INTERNAL)
    by_id = {i["id"]: (i["name"], i["price"], i["available"]) for i in resp.json()}
    assert by_id == {
        1: ("Burger bò", 45000, True),
        2: ("Khoai tây chiên", 25000, True),
        3: ("Coca-Cola", 15000, True),
        4: ("Gà rán", 60000, False),
    }
