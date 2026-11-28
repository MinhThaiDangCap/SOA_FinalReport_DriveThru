"""Kiểm tra nhanh toàn bộ hệ thống đang chạy thật (Docker + PostgreSQL), đi qua gateway.

Chạy sau khi `docker compose up -d --build` (chỉ cần Python 3, không cần cài thêm gì):

    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url https://<domain>.ngrok-free.app   # qua ngrok

Script đi hết một vòng nghiệp vụ như người dùng thật và dừng ở bước đầu tiên bị sai:
đăng nhập 4 vai trò -> xem menu -> đặt trước, nhận mã -> trạm 1 đọc mã, thu tiền mặt
-> bếp làm món (đơn nhanh trước) -> trạm 2 giao món -> khách đánh giá
-> trạm 1 nhận đơn trả ZaloPay, tạo giao dịch -> kiểm tra bảo mật (token, phân quyền, /internal).
Dữ liệu tạo ra là đơn và đánh giá thật trong database (tài khoản mẫu, cửa hàng 1).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

PASSWORD = "Password123"  # mật khẩu của tài khoản mẫu (auth-service tự tạo)


class Api:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def call(self, method, path, token=None, body=None, headers=None):
        """Trả về (status, json hoặc text). Không ném lỗi với mã 4xx/5xx."""
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("ngrok-skip-browser-warning", "1")  # bỏ trang cảnh báo của ngrok
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, raw.decode(errors="replace")


passed = 0


def check(name, ok, detail=""):
    global passed
    if not ok:
        print(f"  ✘ {name}")
        if detail:
            print(f"    -> {str(detail)[:300]}")
        print("\nKHÔNG ĐẠT. Xem log: docker compose logs <tên-service>")
        sys.exit(1)
    passed += 1
    print(f"  ✔ {name}")


def expect(api, name, method, path, status, **kw):
    code, data = api.call(method, path, **kw)
    check(f"{name} ({method} {path} -> {code})", code == status, data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()
    api = Api(args.base_url)
    print(f"Kiểm tra hệ thống tại {api.base}\n")

    print("1. Đăng nhập (auth-service)")
    tokens = {}
    for role, email in (("khách", "khachhang@drivethru.vn"),
                        ("nhân viên trạm", "staff1@drivethru.vn"),
                        ("bếp", "kitchen1@drivethru.vn"),
                        ("admin", "admin@drivethru.vn")):
        data = expect(api, f"Đăng nhập {role}", "POST", "/api/auth/login", 200,
                      body={"email": email, "password": PASSWORD})
        tokens[role] = data["access_token"]
    customer, staff, kitchen, admin = (tokens["khách"], tokens["nhân viên trạm"],
                                       tokens["bếp"], tokens["admin"])
    expect(api, "Sai mật khẩu bị từ chối", "POST", "/api/auth/login", 401,
           body={"email": "khachhang@drivethru.vn", "password": "SaiMatKhau1"})

    print("\n2. Xem menu (menu-service)")
    stations = expect(api, "Danh sách cửa hàng", "GET", "/api/menu/stations", 200)
    check("Có cửa hàng đang hoạt động", any(s["id"] == 1 for s in stations), stations)
    menu = expect(api, "Menu cửa hàng 1", "GET", "/api/menu/stations/1/menu", 200)
    items = [i for c in menu["categories"] for i in c["items"] if i["available"]]
    check("Có món còn hàng", len(items) >= 1, menu)
    item = items[0]

    def place(qty):
        return expect(api, f"Đặt trước {qty} phần", "POST", "/api/orders", 201, token=customer, body={
            "station_id": 1, "license_plate": "51A-999.99", "contact_phone": "0909999999",
            "arrival_minutes": 15, "items": [{"menu_item_id": item["id"], "quantity": qty}],
        })

    print("\n3. Đặt trước trên web (order-service gọi menu-service)")
    order = place(2)
    oid, code = order["id"], order["pickup_code"]
    check("Giá tính ở server", order["total_amount"] == item["price"] * 2, order)
    check(f"Có mã nhận món 4 số ({code}), đơn đang giữ chỗ (HOLD)",
          order["status"] == "HOLD" and len(code or "") == 4, order)
    check("Chưa vào bếp nên chưa có giờ xong", order.get("estimated_ready_at") is None, order)

    print("\n4. Trạm 1: đọc mã, thu tiền mặt (order-service, payment-service)")
    found = expect(api, "Tìm đơn theo mã", "GET", f"/api/orders/station/lookup?q={code}", 200, token=staff)
    check("Tìm đúng đơn", [o["id"] for o in found] == [oid], found)
    expect(api, "Bếp không nhận đơn ở trạm 1 -> 403", "POST", f"/api/orders/{oid}/check-in", 403,
           token=kitchen, body={"payment_method": "CASH"})
    expect(api, "Chưa nhận đơn thì chưa thu tiền", "POST", "/api/payments/cash/confirm", 409,
           token=staff, body={"order_id": oid})
    expect(api, "Nhận đơn, khách trả tiền mặt", "POST", f"/api/orders/{oid}/check-in", 200,
           token=staff, body={"payment_method": "CASH"})
    expect(api, "Đã thu tiền mặt, đơn vào bếp", "POST", "/api/payments/cash/confirm", 200,
           token=staff, body={"order_id": oid})
    order = expect(api, "Xem đơn", "GET", f"/api/orders/{oid}", 200, token=customer)
    check("Đơn đã vào bếp (CONFIRMED) và có giờ xong", order["status"] == "CONFIRMED"
          and bool(order.get("estimated_ready_at")), order)

    print("\n5. Bếp làm món, trạm 2 giao")
    quick = place(1)
    expect(api, "Nhận đơn thứ 2", "POST", f"/api/orders/{quick['id']}/check-in", 200,
           token=staff, body={"payment_method": "CASH"})
    expect(api, "Thu tiền đơn thứ 2", "POST", "/api/payments/cash/confirm", 200,
           token=staff, body={"order_id": quick["id"]})
    queue = expect(api, "Hàng đợi bếp", "GET", "/api/orders/kitchen", 200, token=kitchen)
    ids = [o["id"] for o in queue]
    check("Bếp thấy cả 2 đơn đã trả tiền", oid in ids and quick["id"] in ids, ids)
    expect(api, "Nhân viên trạm không làm việc của bếp -> 403", "PATCH", f"/api/orders/{oid}/status",
           403, token=staff, body={"status": "PREPARING"})
    for st in ("PREPARING", "READY"):
        expect(api, f"Bếp chuyển sang {st}", "PATCH", f"/api/orders/{oid}/status", 200,
               token=kitchen, body={"status": st})
    ready = expect(api, "Trạm 2 thấy đơn đã xong", "GET", "/api/orders/station/ready", 200, token=staff)
    check("Đơn có trong danh sách trạm 2", any(o["id"] == oid for o in ready), ready)
    expect(api, "Bếp không giao món -> 403", "PATCH", f"/api/orders/{oid}/status", 403,
           token=kitchen, body={"status": "COMPLETED"})
    done = expect(api, "Trạm 2 giao món", "PATCH", f"/api/orders/{oid}/status", 200,
                  token=staff, body={"status": "COMPLETED"})
    check("Trạng thái COMPLETED", done["status"] == "COMPLETED", done)
    for st in ("PREPARING", "READY"):
        expect(api, f"Bếp làm đơn thứ 2: {st}", "PATCH", f"/api/orders/{quick['id']}/status", 200,
               token=kitchen, body={"status": st})
    expect(api, "Trạm 2 giao đơn thứ 2", "PATCH", f"/api/orders/{quick['id']}/status", 200,
           token=staff, body={"status": "COMPLETED"})
    expect(api, "Thời gian chờ các cửa hàng", "GET", "/api/orders/wait-times", 200)

    print("\n6. Khách đánh giá (feedback-service gọi order-service)")
    expect(api, "Đánh giá 1 sao không lý do bị chặn", "POST", "/api/reviews", 422,
           token=customer, body={"order_id": oid, "rating": 1})
    expect(api, "Gửi đánh giá 5 sao", "POST", "/api/reviews", 201,
           token=customer, body={"order_id": oid, "rating": 5, "comment": "Kiểm tra tự động"})
    expect(api, "Không đánh giá lại lần 2", "POST", "/api/reviews", 400,
           token=customer, body={"order_id": oid, "rating": 4})
    expect(api, "Thống kê đánh giá cửa hàng 1", "GET", "/api/reviews/stations/1/stats", 200)

    print("\n7. Trạm 1: khách trả ZaloPay trên điện thoại (payment-service gọi ZaloPay)")
    zp = place(1)
    expect(api, "Chưa tới trạm 1 thì chưa tạo được giao dịch", "POST", "/api/payments/zalopay/create",
           409, token=customer, body={"order_id": zp["id"]})
    expect(api, "Trạm 1 nhận đơn, khách chọn ZaloPay", "POST", f"/api/orders/{zp['id']}/check-in", 200,
           token=staff, body={"payment_method": "ZALOPAY"})
    pay = expect(api, "Tạo giao dịch ZaloPay", "POST", "/api/payments/zalopay/create", 201,
                 token=customer, body={"order_id": zp["id"]})
    url = pay.get("payment_url", "")
    mode = "giả lập (PAYMENT_MOCK_MODE=true)" if "/mock/" in url else "ZaloPay sandbox"
    check(f"Có link thanh toán, chế độ: {mode}", url.startswith("http"), pay)
    expect(api, "Hủy đơn chưa trả tiền", "POST", f"/api/orders/{zp['id']}/cancel", 200, token=customer)

    print("\n8. Bảo mật")
    expect(api, "Không có token -> 401", "GET", "/api/orders/me", 401)
    expect(api, "Khách không xem được hàng đợi bếp -> 403", "GET", "/api/orders/kitchen", 403,
           token=customer)
    expect(api, "Khách không tạo được nhân viên -> 403", "POST", "/api/auth/staff", 403,
           token=customer, body={"email": "x@drivethru.vn", "password": PASSWORD,
                                 "full_name": "Nhân Viên X", "station_id": 1})
    expect(api, "Gateway chặn API nội bộ /internal", "GET", "/internal/orders/1", 404,
           headers={"X-Internal-Key": "doan-thu"})
    expect(api, "Gateway chặn /metrics", "GET", "/metrics", 404)
    expect(api, "Admin xem được thống kê đơn", "GET", "/api/orders/stats", 200, token=admin)

    print(f"\nĐẠT: {passed} bước kiểm tra đều đúng.")


if __name__ == "__main__":
    main()
