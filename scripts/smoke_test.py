"""Kiểm tra nhanh toàn bộ hệ thống đang chạy thật (Docker + PostgreSQL), đi qua gateway.

Chạy sau khi `docker compose up -d --build` (chỉ cần Python 3, không cần cài thêm gì):

    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url https://<domain>.ngrok-free.app   # qua ngrok

Script đi hết một vòng nghiệp vụ như người dùng thật và dừng ở bước đầu tiên bị sai:
đăng nhập 3 vai trò -> xem menu -> đặt đơn trả tại quầy -> quầy làm món, thu tiền, giao món
-> khách đánh giá -> tạo giao dịch MoMo -> kiểm tra bảo mật (token, phân quyền, /internal).
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
                        ("nhân viên", "staff1@drivethru.vn"),
                        ("admin", "admin@drivethru.vn")):
        data = expect(api, f"Đăng nhập {role}", "POST", "/api/auth/login", 200,
                      body={"email": email, "password": PASSWORD})
        tokens[role] = data["access_token"]
    customer, staff, admin = tokens["khách"], tokens["nhân viên"], tokens["admin"]
    expect(api, "Sai mật khẩu bị từ chối", "POST", "/api/auth/login", 401,
           body={"email": "khachhang@drivethru.vn", "password": "SaiMatKhau1"})

    print("\n2. Xem menu (menu-service)")
    stations = expect(api, "Danh sách cửa hàng", "GET", "/api/menu/stations", 200)
    check("Có cửa hàng đang hoạt động", any(s["id"] == 1 for s in stations), stations)
    menu = expect(api, "Menu cửa hàng 1", "GET", "/api/menu/stations/1/menu", 200)
    items = [i for c in menu["categories"] for i in c["items"] if i["available"]]
    check("Có món còn hàng", len(items) >= 1, menu)
    item = items[0]

    print("\n3. Đặt đơn trả tại quầy (order-service gọi menu-service)")
    order = expect(api, "Tạo đơn", "POST", "/api/orders", 201, token=customer, body={
        "station_id": 1, "license_plate": "51A-99999", "payment_method": "CASH",
        "items": [{"menu_item_id": item["id"], "quantity": 2}],
    })
    oid = order["id"]
    check("Giá tính ở server", order["total_amount"] == item["price"] * 2, order)
    check("Đơn tiền mặt vào thẳng hàng đợi (CONFIRMED)", order["status"] == "CONFIRMED", order)
    check("Có giờ xong dự kiến", bool(order.get("estimated_ready_at")), order)
    expect(api, "Thời gian chờ các cửa hàng", "GET", "/api/orders/wait-times", 200)

    print("\n4. Quầy xử lý đơn (order-service, payment-service)")
    queue = expect(api, "Hàng đợi của nhân viên", "GET", "/api/orders/queue", 200, token=staff)
    check("Đơn mới có trong hàng đợi", any(o["id"] == oid for o in queue))
    for st in ("PREPARING", "READY"):
        expect(api, f"Chuyển sang {st}", "PATCH", f"/api/orders/{oid}/status", 200,
               token=staff, body={"status": st})
    expect(api, "Chưa thu tiền thì không hoàn thành được", "PATCH", f"/api/orders/{oid}/status",
           409, token=staff, body={"status": "COMPLETED"})
    expect(api, "Ghi nhận đã thu tiền mặt", "POST", "/api/payments/cash/confirm", 200,
           token=staff, body={"order_id": oid})
    done = expect(api, "Giao món, hoàn thành đơn", "PATCH", f"/api/orders/{oid}/status", 200,
                  token=staff, body={"status": "COMPLETED"})
    check("Trạng thái COMPLETED", done["status"] == "COMPLETED", done)

    print("\n5. Khách đánh giá (feedback-service gọi order-service)")
    expect(api, "Đánh giá 1 sao không lý do bị chặn", "POST", "/api/reviews", 422,
           token=customer, body={"order_id": oid, "rating": 1})
    expect(api, "Gửi đánh giá 5 sao", "POST", "/api/reviews", 201,
           token=customer, body={"order_id": oid, "rating": 5, "comment": "Kiểm tra tự động"})
    expect(api, "Không đánh giá lại lần 2", "POST", "/api/reviews", 400,
           token=customer, body={"order_id": oid, "rating": 4})
    expect(api, "Thống kê đánh giá cửa hàng 1", "GET", "/api/reviews/stations/1/stats", 200)

    print("\n6. Thanh toán MoMo (payment-service gọi MoMo sandbox)")
    momo_order = expect(api, "Tạo đơn MoMo", "POST", "/api/orders", 201, token=customer, body={
        "station_id": 1, "license_plate": "51A-99999", "payment_method": "MOMO",
        "items": [{"menu_item_id": item["id"], "quantity": 1}],
    })
    check("Đơn MoMo chờ thanh toán", momo_order["status"] == "PENDING_PAYMENT", momo_order)
    pay = expect(api, "Tạo giao dịch MoMo", "POST", "/api/payments/momo/create", 201,
                 token=customer, body={"order_id": momo_order["id"]})
    url = pay.get("payment_url", "")
    mode = "giả lập (PAYMENT_MOCK_MODE=true)" if "/mock/" in url else "MoMo sandbox"
    check(f"Có link thanh toán, chế độ: {mode}", url.startswith("http"), pay)
    expect(api, "Hủy đơn MoMo chưa trả", "POST", f"/api/orders/{momo_order['id']}/cancel", 200,
           token=customer)

    print("\n7. Bảo mật")
    expect(api, "Không có token -> 401", "GET", "/api/orders/me", 401)
    expect(api, "Khách không xem được hàng đợi quầy -> 403", "GET", "/api/orders/queue", 403,
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
