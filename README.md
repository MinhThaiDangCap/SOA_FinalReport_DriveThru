# GoLane – Drive-Thru Ordering System

Hệ thống đặt món trước cho **GoLane**, chuỗi cửa hàng đồ ăn nhanh theo mô hình drive-thru (giả lập một doanh nghiệp), xây dựng theo **kiến trúc Microservices** (đồ án môn Kiến trúc hướng dịch vụ).

Khách chọn cửa hàng, đặt món và thanh toán online (ZaloPay) hoặc trả tại quầy, sau đó lái xe tới nhận món. Nhân viên cập nhật trạng thái đơn, khách đánh giá sau khi nhận món, admin theo dõi hệ thống qua Grafana.

---

## Mục lục
1. [Kiến trúc](#1-kiến-trúc)
2. [Công nghệ](#2-công-nghệ)
3. [Cài đặt và chạy bằng Docker](#3-cài-đặt-và-chạy-bằng-docker)
4. [Dùng thử](#4-dùng-thử)
5. [Thanh toán ZaloPay](#5-thanh-toán-zalopay)
6. [Lệnh thường dùng](#6-lệnh-thường-dùng)
7. [Chạy test](#7-chạy-test)
8. [Xử lý lỗi thường gặp](#8-xử-lý-lỗi-thường-gặp)
9. [Cấu trúc thư mục](#9-cấu-trúc-thư-mục)
10. [Câu hỏi vấn đáp thường gặp](#10-câu-hỏi-vấn-đáp-thường-gặp)

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
     └───────────────┴──────── PostgreSQL :5432 (5 database, 5 tài khoản riêng) ──┘

  order-service ──▶ menu-service      (lấy giá món, kiểm tra còn hàng, số phút làm món)
  payment-service ─▶ order-service    (xác nhận đã thanh toán)
  order-service ──▶ payment-service   (kiểm tra đơn đã thanh toán trước khi hủy / đổi / giao)
  feedback-service ─▶ order-service   (kiểm tra đơn đã hoàn thành)
  payment-service ─▶ ZaloPay sandbox  (tạo đơn, nhận callback, tra cứu trạng thái)

  prometheus :9090 ──▶ grafana :3000
```

| Service | Cổng | Database | Chức năng |
|---|---|---|---|
| `auth-service` | 8001 | `auth_db` | Đăng ký, đăng nhập, JWT, quản lý nhân viên |
| `menu-service` | 8002 | `menu_db` | Cửa hàng, danh mục, món ăn, tình trạng còn/hết món |
| `order-service` | 8003 | `order_db` | Đặt đơn, mã giảm giá, hàng đợi, trạng thái đơn |
| `payment-service` | 8004 | `payment_db` | Thanh toán ZaloPay, thu tiền mặt |
| `feedback-service` | 8005 | `feedback_db` | Đánh giá 1–5 sao, thống kê theo cửa hàng |
| `gateway` | **8080** | — | Giao diện web và định tuyến API tới các service |
| `prometheus` / `grafana` | 9090 / 3000 | — | Thu thập metrics và dashboard giám sát |

**Nguyên tắc chính:**
- Mỗi service có database riêng **và tài khoản PostgreSQL riêng** (`auth_user`, `menu_user`, `order_user`, `payment_user`, `feedback_user`). Tài khoản của service này bị PostgreSQL từ chối khi vào database của service khác, nên muốn lấy dữ liệu bắt buộc phải gọi API. Kiểm tra bằng `bash scripts/check-db-isolation.sh`.
- Gọi nội bộ giữa các service đi qua `/internal/...`, kèm header `X-Internal-Key`. Gateway chặn mọi đường `/internal/` từ bên ngoài.
- JWT do `auth-service` phát, các service khác tự kiểm tra bằng cùng `JWT_SECRET`.
- Giá tiền luôn tính ở server, không tin giá client gửi lên.

**Trạng thái đơn hàng:**
```
PENDING_PAYMENT ──▶ CONFIRMED ──▶ PREPARING ──▶ READY ──▶ COMPLETED
       │                │                         ▲  │
       └──▶ CANCELLED ◀─┘                ARRIVED ─┘◀─┘   (khách báo "Tôi đã đến")
```
Đơn trả tại quầy bắt đầu luôn ở `CONFIRMED`. Đơn ZaloPay chuyển sang `CONFIRMED` khi thanh toán thành công.

**Ước lượng giờ xong đơn:**
- Mỗi món có số phút làm cố định (`prep_minutes`, admin sửa trong trang Thực đơn). Mỗi cửa hàng có số đơn bếp làm được cùng lúc (`kitchen_capacity`, sửa trong trang Cửa hàng).
- Thời gian làm 1 đơn = món lâu nhất + 1 phút cho mỗi 2 phần thêm.
- Giờ xong dự kiến = bây giờ + (phút còn lại của các đơn xếp trước ÷ số đơn làm cùng lúc) + thời gian làm đơn đó. Tính khi đơn vào hàng đợi và tính lại khi bếp bấm "Bắt đầu làm".
- Khách thấy "Dự kiến xong lúc …" ở trang đơn; màn hình quầy tô đỏ đơn trễ hẹn. Code: `services/order-service/app/estimate.py`.

---

## 2. Công nghệ

| Phần | Công nghệ |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Database | PostgreSQL 16 |
| Frontend | React 18, Vite, React Router |
| Gateway | nginx |
| Thanh toán | ZaloPay sandbox (API v2) |
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
```
Bản nộp nằm ở nhánh `main`. Nhánh đang phát triển là `feature/integration`.

### 3.3. Cấu hình (không bắt buộc)

**Không cần file `.env` vẫn chạy được.** `docker-compose.yml` đã có giá trị mặc định cho mọi biến, kể cả bộ key sandbox công khai của ZaloPay.

Chỉ tạo file `.env` ở thư mục gốc khi muốn đổi giá trị. File này **không được commit** (đã có trong `.gitignore`).

| Biến | Khi nào cần |
|---|---|
| `JWT_SECRET`, `INTERNAL_KEY` | Muốn dùng giá trị bí mật riêng (nên đổi khi demo) |
| `ZALOPAY_APP_ID`, `ZALOPAY_KEY1`, `ZALOPAY_KEY2` | Có tài khoản ZaloPay riêng. Để trống = key sandbox công khai (app_id `2554`) |
| `NGROK_AUTHTOKEN`, `NGROK_DOMAIN`, `ZALOPAY_CALLBACK_URL`, `ZALOPAY_REDIRECT_URL` | Cho ZaloPay gọi callback thật qua internet (xem [mục 5](#5-thanh-toán-zalopay)) |
| `PAYMENT_MOCK_MODE=true` | Thanh toán giả, không gọi ZaloPay (dự phòng khi demo mất mạng) |
| `AUTH_DB_PASSWORD`, `MENU_DB_PASSWORD`, `ORDER_DB_PASSWORD`, `PAYMENT_DB_PASSWORD`, `FEEDBACK_DB_PASSWORD` | Đổi mật khẩu tài khoản database của từng service. Chỉ có tác dụng khi database được tạo mới (`docker compose down -v`) |

Mẫu đầy đủ ở `.env.example`. **Lưu ý:** nếu copy từ `.env.example`, giữ `ZALOPAY_REDIRECT_URL=http://localhost:8080/payment/result` khi chạy bằng Docker.

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

> **Máy đã từng chạy bản cũ** (trước khi tách tài khoản database): chạy **một lần** `docker compose down -v` rồi `docker compose up -d --build`. Lệnh này xóa dữ liệu cũ; tài khoản mẫu, cửa hàng, món và đánh giá mẫu sẽ tự tạo lại. Nếu bỏ qua, các service sẽ báo `password authentication failed for user "..._user"`.

**Kiểm tra cả hệ thống** (chỉ cần Python 3):
```bash
python scripts/smoke_test.py
```
Script đi hết một vòng: đăng nhập 3 vai trò → đặt đơn → quầy làm món, thu tiền, giao món → đánh giá → tạo giao dịch ZaloPay → kiểm tra phân quyền và gateway. Cuối cùng in `ĐẠT: 36 bước kiểm tra đều đúng.`

**Kiểm tra mỗi service chỉ vào được database của mình:**
```bash
bash scripts/check-db-isolation.sh
```
(Trên Windows chạy trong **Git Bash**.) Kết quả là bảng 5 tài khoản × 5 database, chỉ đường chéo "vào được".

---

## 4. Dùng thử

| Trang | Địa chỉ |
|---|---|
| **Web** | http://localhost:8080 |
| Swagger từng service | http://localhost:8001/docs … http://localhost:8005/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (`admin` / `admin`) → **Dashboards** → *Drive-Thru Microservices & Business Monitoring* |

**Tài khoản mẫu** (`auth-service` tự tạo khi khởi động, mật khẩu đều là `Password123`; có thể bấm **Đăng ký** để tạo khách mới):

| Vai trò | Email | Cửa hàng |
|---|---|---|
| Admin | `admin@drivethru.vn` | Toàn hệ thống |
| Nhân viên | `staff1@drivethru.vn` / `staff2@…` / `staff3@…` | 1 Quận 7 / 2 Thủ Đức / 3 Bình Thạnh |
| Khách hàng | `khachhang@drivethru.vn` | — |

**Kịch bản nên thử:**
1. **Trả tại quầy:** đăng nhập khách → chọn cửa hàng → thêm món → đặt đơn, chọn "Trả tại quầy" → xem tiến trình đơn.
2. **ZaloPay:** đặt đơn chọn ZaloPay → được chuyển sang trang ZaloPay sandbox (xem [mục 5](#5-thanh-toán-zalopay)).
3. **Nhân viên xử lý đơn:** đăng nhập tài khoản nhân viên, web tự mở **Màn hình quầy** (`/staff`):
   - Tab **Đơn hàng**: đơn chia 3 cột *Đơn mới → Đang làm → Chờ giao*, tự cập nhật mỗi 5 giây. Mỗi thẻ có biển số xe và đúng một nút: "Bắt đầu làm" → "Món đã xong" → "Đã giao món" (đơn tiền mặt là "Thu … & giao món"). Khách bấm "Tôi đã đến" thì thẻ được tô viền đỏ.
   - Tab **Món hôm nay**: bật/tắt món hết hàng của cửa hàng mình.
   - Tab **Đánh giá**: điểm trung bình và đánh giá của khách.
   - Đơn trả tại quầy **bắt buộc ghi nhận đã thu tiền** mới được hoàn thành.
4. **Admin:** đăng nhập tài khoản admin, web mở **Quản trị** (`/admin`) gồm: Tổng quan (doanh thu, số đơn, đánh giá theo cửa hàng), Đơn hàng (xem và xử lý đơn mọi cửa hàng), Cửa hàng, Thực đơn (danh mục và món), Nhân viên (tạo, khóa tài khoản), Mã giảm giá, Đánh giá.
5. **Đánh giá:** khi đơn `COMPLETED`, khách mở lại đơn sẽ thấy ô chấm sao. Đánh giá 1–2 sao bắt buộc ghi lý do.
6. **Hủy đơn:** khách hủy được đơn ZaloPay **chưa thanh toán** và đơn trả tại quầy (khi bếp chưa làm). Đơn **đã thanh toán ZaloPay thì không hủy được trên ứng dụng**: trang đơn hiện hotline cửa hàng `1900 6868` để khách gọi, cửa hàng hủy đơn và hoàn tiền (ngoài phạm vi hệ thống, xem [mục 5](#5-thanh-toán-zalopay)). Trước khi hủy đơn đang chờ, hệ thống hỏi lại ZaloPay để không hủy nhầm đơn khách vừa quét mã xong.
7. **Đổi phương thức thanh toán:** chỉ đơn ZaloPay **chưa trả tiền** đổi được sang trả tại quầy (đơn vào hàng đợi ngay). Đơn trả tại quầy đã gửi tới cửa hàng nên không đổi sang ZaloPay được, để đơn không bị rút khỏi màn hình quầy khi bếp sắp làm; muốn trả online thì hủy (khi bếp chưa làm) và đặt lại. ZaloPay đã trả là chốt.

---

## 5. Thanh toán ZaloPay

Hệ thống dùng **ZaloPay sandbox** (API v2) với bộ key sandbox công khai (`app_id` 2554), không cần đăng ký tài khoản, không có tiền thật.

**Luồng:**
1. Web gọi `POST /api/payments/zalopay/create` → payment-service gọi API `v2/create` của ZaloPay (ký HMAC-SHA256 bằng `key1`), nhận `order_url` → chuyển khách sang trang ZaloPay.
2. Khách thanh toán trên trang ZaloPay: quét QR bằng app **Zalopay sandbox**, thẻ ATM nội địa hoặc thẻ quốc tế.
3. ZaloPay gọi **callback** `POST /api/payments/zalopay/callback` (server-to-server). payment-service kiểm tra `mac` bằng `key2` và số tiền, rồi báo order-service chuyển đơn sang `CONFIRMED`. Mỗi giao dịch chỉ được xử lý một lần.
4. ZaloPay chuyển khách về `/payment/result`. Web gọi `GET /api/payments/zalopay/return` (kiểm tra `checksum` bằng `key2`, khách không sửa URL để gian lận được). Nếu callback chưa tới, payment-service tự hỏi ZaloPay bằng API `v2/query` có ký, nên **chạy local không có ngrok vẫn xác nhận được đơn**.

**Hủy đơn đã thanh toán: ngoài phạm vi đề tài.**
Đơn ZaloPay đã thanh toán thì khách **không tự hủy trên ứng dụng**. Trang đơn hiện hotline `1900 6868`; khách gọi cửa hàng, cửa hàng hủy đơn và hoàn tiền trên trang quản lý của ZaloPay. Hệ thống chỉ xử lý hủy đơn **chưa thanh toán**:
- Trước khi hủy (hoặc đổi sang trả tại quầy) một đơn đang chờ, order-service gọi `GET /internal/payments/order/{id}/paid?sync=true`. payment-service hỏi lại ZaloPay các giao dịch còn chờ: khách vừa quét mã xong mà callback chưa tới thì đơn được xác nhận và không bị hủy nhầm.
- Nếu tiền vẫn về sau khi đơn đã hủy (hiếm), giao dịch được ghi nhận kèm ghi chú để cửa hàng hoàn tiền qua hotline.

**Dữ liệu test** (theo [Zalopay Docs](https://docs.zalopay.vn/docs/developer-tools/test-instructions/testing)):
- **Thẻ ATM nội địa** (chọn *Thẻ/tài khoản nội địa*): `9704540000000062`, tên `NGUYEN VAN A`, ngày phát hành `10/18`. Thẻ báo lỗi để thử trường hợp thất bại: `9704540000000013` (thẻ mất), `9704540000000047` (không đủ tiền).
- **Quét QR**: cài app Zalopay sandbox ở trang [Test wallets](https://docs.zalopay.vn/docs/developer-tools/test-instructions/test-wallets), đăng ký bằng số điện thoại (mã xác thực `111111`), nạp tiền ảo ở mục *Deposit* của trang đó. App Zalopay thật không quét được QR sandbox.

**Cho ZaloPay gọi callback thật qua ngrok (khi demo):**

ngrok mở một địa chỉ công khai trỏ vào máy bạn. Địa chỉ callback được gửi kèm mỗi giao dịch nên key sandbox công khai vẫn nhận được callback.

1. Tạo tài khoản miễn phí tại https://ngrok.com. Trong dashboard lấy **authtoken** (mục *Your Authtoken*) và **domain miễn phí** dạng `xxxx.ngrok-free.app` (mục *Domains*, chưa có thì tạo).
   - Mỗi người dùng token và domain của chính mình. Một domain không chạy cùng lúc ở hai máy (lỗi `ERR_NGROK_334`).
   - **Không** ghi token vào file nào được push lên GitHub (kể cả `.env.example`). Lỡ push thì vào dashboard ngrok xóa token đó và tạo token mới.
2. Thêm vào `.env` (domain viết không có `https://` và không có `/` ở cuối):
   ```
   NGROK_AUTHTOKEN=<token của bạn>
   NGROK_DOMAIN=<domain của bạn>
   ZALOPAY_REDIRECT_URL=https://<domain của bạn>/payment/result
   ZALOPAY_CALLBACK_URL=https://<domain của bạn>/api/payments/zalopay/callback
   ```
3. Bật tunnel và áp dụng cấu hình mới cho payment-service:
   ```bash
   docker compose --profile tunnel up -d ngrok
   docker compose up -d payment-service
   ```
4. Kiểm tra:
   - `docker logs drivethru_ngrok --tail 20` phải báo tunnel online với đúng domain. Nếu báo `unknown flag: --url`, đổi `--url=` thành `--domain=` trong `command` của service `ngrok` ở `docker-compose.yml`.
   - `docker compose exec payment-service printenv ZALOPAY_CALLBACK_URL ZALOPAY_REDIRECT_URL` phải in 2 link bắt đầu bằng `https://<domain của bạn>`.
   - Mở `https://<domain của bạn>/` (gặp trang cảnh báo của ngrok thì bấm **Visit Site**), hoặc chạy `python scripts/smoke_test.py --base-url https://<domain của bạn>`.
5. Đặt một đơn ZaloPay **ngay trên link ngrok** (đăng nhập trên link đó; phiên đăng nhập ở `localhost:8080` không dùng chung). Thanh toán xong, mở http://localhost:4040 và lọc chữ `zalopay`: thấy `POST /api/payments/zalopay/callback` là ZaloPay đã gọi callback thật (có thể chậm vài giây).

**Sau khi demo:**
- Tắt tunnel: `docker compose --profile tunnel stop ngrok`. Khi tunnel bật, ai có link cũng vào được hệ thống (gateway vẫn chặn `/internal/` và `/metrics`).
- Đặt lại `ZALOPAY_REDIRECT_URL=http://localhost:8080/payment/result` (hoặc xóa các dòng ZaloPay/ngrok trong `.env`), rồi `docker compose up -d payment-service`.
- Mở `/api/payments/zalopay/callback` bằng trình duyệt ra `405 Method Not Allowed` là bình thường, vì route này chỉ nhận POST.

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
| Vào database (tài khoản quản trị) | `docker exec -it drivethru_postgres psql -U admin -d order_db` |
| Kiểm tra cả hệ thống | `python scripts/smoke_test.py` |
| Kiểm tra phân quyền database | `bash scripts/check-db-isolation.sh` |
| Demo: service không vào được database khác | `docker exec -it drivethru_postgres psql -U order_user -d payment_db` → `permission denied` |

Xem database bằng TablePlus/DBeaver: host `localhost`, port `5432`, user `admin`, mật khẩu `secretpassword` (giá trị mặc định trong `docker-compose.yml`). Tài khoản `admin` chỉ để quản trị; các service dùng tài khoản riêng (mặc định `auth_user` / `auth_secret`, `menu_user` / `menu_secret`, …).

---

## 7. Chạy test

Có 2 lớp kiểm thử:
- **Test API của từng service** (pytest, 81 test): chạy bằng SQLite trong bộ nhớ nên **không cần Postgres hay Docker**. Cần Python 3.12+.
- **Kiểm tra hệ thống thật** (`scripts/smoke_test.py`, 36 bước) và **phân quyền database** (`scripts/check-db-isolation.sh`): chạy với Docker đang bật, xem [mục 3.4](#34-build-và-chạy).

```bash
cd services/payment-service
pip install -r requirements.txt pytest
python -m pytest -q tests
```

| Service | Lệnh (đứng trong thư mục service) | Số test |
|---|---|---|
| `auth-service` | `python -m pytest -q test_auth.py` | 12 |
| `services/menu-service` | `python -m pytest -q tests` | 20 |
| `services/order-service` | `python -m pytest -q tests` | 23 |
| `services/payment-service` | `python -m pytest -q tests` | 14 |
| `feeback-service` | `python -m pytest -q test_reviews.py` | 12 |

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
| Thanh toán ZaloPay xong bị chuyển tới trang không mở được | Kiểm tra `ZALOPAY_REDIRECT_URL` trong `.env` trỏ đúng `http://localhost:8080/payment/result` (hoặc link ngrok) |
| `password authentication failed for user "..._user"` | Database tạo từ bản cũ (trước khi tách tài khoản) hoặc vừa đổi `*_DB_PASSWORD`. Chạy `docker compose down -v` rồi `docker compose up -d --build` |
| `init-dbs.sh: line 1: $'\r': command not found` trong log postgres | File bị đổi xuống dòng kiểu Windows. Xóa file rồi lấy lại từ Git theo `.gitattributes`: `rm init-dbs.sh` rồi `git checkout -- init-dbs.sh`, sau đó `docker compose down -v` và chạy lại |
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
│   └── payment-service/     # ZaloPay, tiền mặt
├── frontend/                # React + Vite, build ra nginx làm gateway
├── monitoring/              # Cấu hình Prometheus và dashboard Grafana
├── scripts/                 # smoke_test.py (kiểm tra hệ thống), check-db-isolation.sh
├── docs/                    # Use Case, ERD, sơ đồ kiến trúc, máy trạng thái đơn
├── init-dbs.sh              # Tạo 5 database + 5 tài khoản riêng khi Postgres khởi động lần đầu
├── docker-compose.yml       # Chạy toàn bộ hệ thống
└── .env.example             # Mẫu biến môi trường
```

---

## 10. Câu hỏi vấn đáp thường gặp

**Các service biết người dùng là ai mà không cần hỏi lại auth-service?**
`auth-service` ký JWT (HS256) chứa `sub`, `role`, `station_id`. Service khác tự kiểm tra chữ ký bằng cùng `JWT_SECRET`, nên không gọi sang auth-service mỗi request và auth-service không thành điểm nghẽn.

**Không có khóa ngoại giữa các database thì giữ dữ liệu đúng bằng cách nào?**
Các ID như `reviews.order_id` chỉ là tham chiếu logic. Trước khi ghi, service gọi API nội bộ của service sở hữu dữ liệu để kiểm tra, ví dụ feedback-service gọi `/internal/orders/{id}` (kèm `X-Internal-Key`, timeout 3 giây, retry 2 lần) để chắc đơn đã `COMPLETED` và đúng chủ. Đơn hàng lưu sẵn tên và giá món lúc đặt (snapshot) nên không phụ thuộc menu-service về sau.

**Lấy gì chứng minh service này không đọc database của service khác?**
Mỗi service có tài khoản PostgreSQL riêng. `docker exec -it drivethru_postgres psql -U order_user -d payment_db` bị từ chối `permission denied`; `bash scripts/check-db-isolation.sh` in bảng đủ 5 × 5 trường hợp.

**Khách chấm 1–2 sao thì sao?**
Bắt buộc ghi lý do (thiếu thì trả `422`). Metric `negative_reviews_total` tăng theo từng cửa hàng và hiện ở Grafana, admin xem chi tiết ở tab Đánh giá.

**Sao khách không tự hủy được đơn đã thanh toán?**
Hủy đơn đã thanh toán kéo theo hoàn tiền, là nghiệp vụ của cửa hàng nên nằm ngoài phạm vi đề tài. Khách gọi hotline, cửa hàng hủy đơn và hoàn tiền trên trang quản lý của ZaloPay. Hệ thống chỉ cho hủy đơn chưa thanh toán, và trước khi hủy luôn hỏi lại ZaloPay để không hủy nhầm đơn khách vừa trả xong.
