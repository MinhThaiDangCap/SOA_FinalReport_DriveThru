# GoLane – Drive-Thru Ordering System

Hệ thống đặt món trước cho **GoLane**, chuỗi cửa hàng đồ ăn nhanh theo mô hình drive-thru (giả lập một doanh nghiệp), xây dựng theo **kiến trúc Microservices** (đồ án môn Kiến trúc hướng dịch vụ).

Khách chọn cửa hàng, đặt món và thanh toán online (MoMo) hoặc trả tại quầy, sau đó lái xe tới nhận món. Nhân viên cập nhật trạng thái đơn, khách đánh giá sau khi nhận món, admin theo dõi hệ thống qua Grafana.

---

## Mục lục
1. [Kiến trúc](#1-kiến-trúc)
2. [Công nghệ](#2-công-nghệ)
3. [Cài đặt và chạy bằng Docker](#3-cài-đặt-và-chạy-bằng-docker)
4. [Dùng thử](#4-dùng-thử)
5. [Thanh toán MoMo](#5-thanh-toán-momo)
6. [Lệnh thường dùng](#6-lệnh-thường-dùng)
7. [Chạy test](#7-chạy-test)
8. [Xử lý lỗi thường gặp](#8-xử-lý-lỗi-thường-gặp)
9. [Cấu trúc thư mục](#9-cấu-trúc-thư-mục)

---

## 1. Kiến trúc

```
                         ┌──────────────────────────────┐
  Trình duyệt ──────────▶│  gateway (nginx + React)     │ :8080
                         └──────────────┬───────────────┘
                                        │ /api/...
     ┌───────────────┬──────────────────┼────────────────┬──────────────────┐
     ▼               ▼                  ▼                ▼                  ▼
 auth-service   menu-service      order-service    payment-service   feedback-service
   :8001           :8002              :8003            :8004              :8005
     │               │                  │                │                  │
     └───────────────┴──────── PostgreSQL :5432 (5 database riêng) ─────────┘

  order-service ──▶ menu-service      (lấy giá món, kiểm tra còn hàng)
  payment-service ─▶ order-service    (xác nhận đã thanh toán)
  order-service ──▶ payment-service   (hoàn tiền khi khách hủy đơn đã trả)
  feedback-service ─▶ order-service   (kiểm tra đơn đã hoàn thành)
  payment-service ─▶ MoMo sandbox     (tạo giao dịch, nhận IPN, hoàn tiền)

  prometheus :9090 ──▶ grafana :3000
```

| Service | Cổng | Database | Chức năng |
|---|---|---|---|
| `auth-service` | 8001 | `auth_db` | Đăng ký, đăng nhập, JWT, quản lý nhân viên |
| `menu-service` | 8002 | `menu_db` | Cửa hàng, danh mục, món ăn, tình trạng còn/hết món |
| `order-service` | 8003 | `order_db` | Đặt đơn, mã giảm giá, hàng đợi, trạng thái đơn |
| `payment-service` | 8004 | `payment_db` | Thanh toán MoMo, thu tiền mặt, hoàn tiền |
| `feedback-service` | 8005 | `feedback_db` | Đánh giá 1–5 sao, thống kê theo cửa hàng |
| `gateway` | **8080** | — | Giao diện web và định tuyến API tới các service |
| `prometheus` / `grafana` | 9090 / 3000 | — | Thu thập metrics và dashboard giám sát |

**Nguyên tắc chính:**
- Mỗi service có database riêng, không đọc database của service khác. Cần dữ liệu thì gọi API.
- Gọi nội bộ giữa các service đi qua `/internal/...`, kèm header `X-Internal-Key`. Gateway chặn mọi đường `/internal/` từ bên ngoài.
- JWT do `auth-service` phát, các service khác tự kiểm tra bằng cùng `JWT_SECRET`.
- Giá tiền luôn tính ở server, không tin giá client gửi lên.

**Trạng thái đơn hàng:**
```
PENDING_PAYMENT ──▶ CONFIRMED ──▶ PREPARING ──▶ READY ──▶ COMPLETED
       │                │                         ▲  │
       └──▶ CANCELLED ◀─┘                ARRIVED ─┘◀─┘   (khách báo "Tôi đã đến")
```
Đơn trả tại quầy bắt đầu luôn ở `CONFIRMED`. Đơn MoMo chuyển sang `CONFIRMED` khi thanh toán thành công.

---

## 2. Công nghệ

| Phần | Công nghệ |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Database | PostgreSQL 16 |
| Frontend | React 18, Vite, React Router |
| Gateway | nginx |
| Thanh toán | MoMo sandbox (API v2) |
| Giám sát | Prometheus, Grafana |
| Đóng gói | Docker, Docker Compose |

---

## 3. Cài đặt và chạy bằng Docker

### 3.1. Cài phần mềm

Chỉ cần **Docker Desktop** và **Git**. Python, Node và Postgres đều đã chạy sẵn trong Docker.

1. Cài **Git** từ https://git-scm.com
2. Cài **Docker Desktop** từ https://www.docker.com/products/docker-desktop
   - Giữ tùy chọn **Use WSL 2** (mặc định) và khởi động lại máy sau khi cài.
   - Nếu Docker báo thiếu WSL: mở PowerShell **bằng quyền Administrator**, chạy `wsl --install` rồi khởi động lại máy.
3. Mở Docker Desktop, đợi góc dưới bên trái báo **Engine running**.

Kiểm tra (mỗi lệnh phải in ra số phiên bản):
```bash
docker version
docker compose version
git --version
```

### 3.2. Lấy code

```bash
git clone https://github.com/MinhThaiDangCap/SOA_FinalReport_DriveThru.git
cd SOA_FinalReport_DriveThru
git checkout feature/integration
```

### 3.3. Cấu hình (không bắt buộc)

**Không cần file `.env` vẫn chạy được.** `docker-compose.yml` đã có giá trị mặc định cho mọi biến, kể cả bộ key test công khai của MoMo.

Chỉ tạo file `.env` ở thư mục gốc khi muốn đổi giá trị. File này **không được commit** (đã có trong `.gitignore`).

| Biến | Khi nào cần |
|---|---|
| `JWT_SECRET`, `INTERNAL_KEY` | Muốn dùng giá trị bí mật riêng (nên đổi khi demo) |
| `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` | Có tài khoản MoMo Business riêng. Để trống = key test công khai |
| `NGROK_AUTHTOKEN`, `MOMO_IPN_URL`, `MOMO_REDIRECT_URL` | Cho MoMo gọi IPN thật qua internet (xem [mục 5](#5-thanh-toán-momo)) |
| `PAYMENT_MOCK_MODE=true` | Thanh toán giả, không gọi MoMo (dự phòng khi demo mất mạng) |

### 3.4. Build và chạy

Đứng ở thư mục gốc repo:
```bash
docker compose up -d --build
```

- Lần đầu mất khoảng 3–10 phút để tải image và build. Các lần sau nhanh hơn.
- Mỗi lần **pull code mới hoặc sửa code** thì chạy lại đúng lệnh này.

Kiểm tra:
```bash
docker compose ps
```
Các container phải ở trạng thái `Up`, riêng `drivethru_postgres` là `Up (healthy)`.

---

## 4. Dùng thử

| Trang | Địa chỉ |
|---|---|
| **Web** | http://localhost:8080 |
| Swagger từng service | http://localhost:8001/docs … http://localhost:8005/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (`admin` / `admin`) |

**Tài khoản mẫu:** `auth-service` tự tạo sẵn 1 admin, 3 nhân viên (`staff1` Quận 7, `staff2` Thủ Đức, `staff3` Bình Thạnh) và 1 khách hàng khi khởi động. Email và mật khẩu xem trong [HUONG_DAN_PHAN_CUA_TAN.md](HUONG_DAN_PHAN_CUA_TAN.md) hoặc hàm `seed_default_accounts` trong [auth-service/main.py](auth-service/main.py). Có thể bấm **Đăng ký** để tạo khách mới.

**Kịch bản nên thử:**
1. **Trả tại quầy:** đăng nhập khách → chọn cửa hàng → thêm món → đặt đơn, chọn "Trả tại quầy" → xem tiến trình đơn.
2. **MoMo:** đặt đơn chọn MoMo → được chuyển sang trang MoMo sandbox (xem [mục 5](#5-thanh-toán-momo)).
3. **Nhân viên xử lý đơn:** đăng nhập tài khoản nhân viên, web tự mở **Màn hình quầy** (`/staff`):
   - Tab **Đơn hàng**: đơn chia 3 cột *Đơn mới → Đang làm → Chờ giao*, tự cập nhật mỗi 5 giây. Mỗi thẻ có biển số xe và đúng một nút: "Bắt đầu làm" → "Món đã xong" → "Đã giao món" (đơn tiền mặt là "Thu … & giao món"). Khách bấm "Tôi đã đến" thì thẻ được tô viền đỏ.
   - Tab **Món hôm nay**: bật/tắt món hết hàng của cửa hàng mình.
   - Tab **Đánh giá**: điểm trung bình và đánh giá của khách.
   - Đơn trả tại quầy **bắt buộc ghi nhận đã thu tiền** mới được hoàn thành.
4. **Admin:** đăng nhập tài khoản admin, web mở **Quản trị** (`/admin`) gồm: Tổng quan (doanh thu, số đơn, đánh giá theo cửa hàng), Đơn hàng (xem và xử lý đơn mọi cửa hàng), Cửa hàng, Thực đơn (danh mục và món), Nhân viên (tạo, khóa tài khoản), Mã giảm giá, Đánh giá.
5. **Đánh giá:** khi đơn `COMPLETED`, khách mở lại đơn sẽ thấy ô chấm sao. Đánh giá 1–2 sao bắt buộc ghi lý do.
6. **Hủy đơn:** khách hủy được khi đơn ở "Chờ thanh toán" hoặc "Đã xác nhận". Đơn MoMo đã trả tiền sẽ được **hoàn tiền về ví trước rồi mới hủy**. Nếu MoMo chưa hoàn được thì đơn giữ nguyên.

---

## 5. Thanh toán MoMo

Hệ thống dùng **MoMo sandbox** với bộ key test công khai, không cần đăng ký tài khoản.

**Luồng thanh toán:**
1. Web gọi `POST /api/payments/momo/create` → payment-service gọi MoMo, nhận `payUrl` → chuyển khách sang trang MoMo.
2. Khách thanh toán xong, MoMo:
   - gọi **IPN** `POST /api/payments/momo/ipn` (server-to-server) để báo kết quả, và
   - chuyển khách về `/payment/result` trên web.
3. payment-service kiểm tra chữ ký HMAC-SHA256 và số tiền, rồi báo order-service chuyển đơn sang `CONFIRMED`. Mỗi giao dịch chỉ được xử lý một lần.

**Thanh toán thành công trên sandbox:** quét QR bằng app **MoMo bản test (UAT)**. App MoMo thường không dùng được. Bấm hủy trên trang MoMo để thử trường hợp thất bại.

**Chạy trên máy cá nhân (mặc định):** MoMo không gọi IPN vào `localhost` được, nên `MOMO_PROCESS_ON_RETURN=true` cho phép trang kết quả tự xác nhận giao dịch. Bước này vẫn kiểm tra chữ ký nên khách không sửa URL để gian lận được.

**Cho MoMo gọi IPN thật (khi demo):**
1. Tạo tài khoản miễn phí tại https://ngrok.com, lấy **authtoken** ở trang Dashboard.
2. Thêm `NGROK_AUTHTOKEN=<token>` vào `.env`.
3. Bật tunnel:
   ```bash
   docker compose --profile tunnel up -d
   ```
4. Mở http://localhost:4040 để lấy link public dạng `https://xxxx.ngrok-free.app`.
5. Thêm vào `.env`:
   ```
   MOMO_IPN_URL=https://xxxx.ngrok-free.app/api/payments/momo/ipn
   MOMO_REDIRECT_URL=https://xxxx.ngrok-free.app/payment/result
   ```
6. Áp dụng: `docker compose up -d payment-service`

Gói ngrok miễn phí đổi link mỗi lần khởi động lại, khi đó làm lại bước 4–6.

---

## 6. Lệnh thường dùng

| Việc cần làm | Lệnh |
|---|---|
| Bật toàn bộ (build lại code mới) | `docker compose up -d --build` |
| Xem trạng thái | `docker compose ps` |
| Xem log một service | `docker compose logs -f payment-service` |
| Khởi động lại một service | `docker compose restart order-service` |
| Build lại một service sau khi sửa code | `docker compose up -d --build payment-service` |
| Tắt hết (giữ dữ liệu) | `docker compose down` |
| Tắt và **xóa sạch database** | `docker compose down -v` |
| Vào database | `docker exec -it drivethru_postgres psql -U admin -d order_db` |

Xem database bằng TablePlus/DBeaver: host `localhost`, port `5432`, user `admin`, mật khẩu `secretpassword` (giá trị mặc định trong `docker-compose.yml`).

---

## 7. Chạy test

Mỗi service có test riêng, chạy bằng SQLite trong bộ nhớ nên **không cần Postgres hay Docker**. Cần Python 3.12+.

```bash
cd services/payment-service
pip install -r requirements.txt pytest
python -m pytest -q tests
```

| Service | Lệnh (đứng trong thư mục service) |
|---|---|
| `auth-service` | `python -m pytest -q test_auth.py` |
| `services/menu-service` | `python -m pytest -q tests` |
| `services/order-service` | `python -m pytest -q tests` |
| `services/payment-service` | `python -m pytest -q tests` |
| `feeback-service` | `python -m pytest -q test_reviews.py` |

Frontend kiểm tra build:
```bash
cd frontend
npm install
npm run build
```

---

## 8. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `port is already allocated` / cổng `5432` bị chiếm | Máy đang có Postgres cài sẵn. Tắt service PostgreSQL trong Windows Services, hoặc sửa `"5432:5432"` thành `"5433:5432"` trong `docker-compose.yml` |
| `Cannot connect to the Docker daemon` | Docker Desktop chưa mở hoặc chưa báo **Engine running** |
| Web báo "Đã có lỗi xảy ra" | `docker compose ps` xem service nào bị `Restarting`, rồi xem log của service đó |
| Service cứ `Restarting` | Thường do Postgres chưa sẵn sàng. Đợi 10 giây rồi `docker compose restart <tên-service>` |
| Sửa code nhưng web không đổi | Quên `--build`. Chạy lại `docker compose up -d --build` |
| Thanh toán MoMo xong bị chuyển tới trang không mở được | Kiểm tra `MOMO_REDIRECT_URL` trong `.env` trỏ đúng `http://localhost:8080/payment/result` (hoặc link ngrok) |
| Muốn làm lại từ đầu | `docker compose down -v` rồi `docker compose up -d --build` |
| Ổ đĩa đầy vì image cũ | `docker system prune` (có hỏi xác nhận trước khi xóa) |

---

## 9. Cấu trúc thư mục

```
SOA_FinalReport_DriveThru/
├── auth-service/            # Đăng ký, đăng nhập, JWT, nhân viên
├── feeback-service/         # Đánh giá và thống kê
├── services/
│   ├── menu-service/        # Cửa hàng, danh mục, món ăn
│   ├── order-service/       # Đơn hàng, mã giảm giá, trạng thái
│   └── payment-service/     # MoMo, tiền mặt, hoàn tiền
├── frontend/                # React + Vite, build ra nginx làm gateway
├── monitoring/              # Cấu hình Prometheus và dashboard Grafana
├── init-dbs.sql             # Tạo 5 database khi Postgres khởi động lần đầu
├── docker-compose.yml       # Chạy toàn bộ hệ thống
├── .env.example             # Mẫu biến môi trường
└── HUONG_DAN_PHAN_CUA_TAN.md  # Chi tiết phần auth, feedback, giám sát
```
