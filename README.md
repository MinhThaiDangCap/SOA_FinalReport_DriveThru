# GoLane – Drive-Thru Ordering System

Hệ thống đặt món trước cho **GoLane**, chuỗi cửa hàng đồ ăn nhanh theo mô hình drive-thru (giả lập một doanh nghiệp), xây dựng theo **kiến trúc Microservices** (đồ án môn Kiến trúc hướng dịch vụ).

Mô hình **2 trạm**: khách đặt trước trên web (chưa trả tiền) và nhận **mã nhận món 4 số**. Tới **trạm 1**, khách đọc mã, nhân viên đối chiếu biển số, khách trả tiền mặt hoặc ZaloPay; lúc này đơn mới vào **bếp**. Khách chờ ở bãi; bếp làm món theo hàng đợi ưu tiên **đơn làm nhanh trước**, in phiếu dán lên túi. Món xong, web mời khách ra **trạm 2** đọc mã nhận món. Khách đánh giá sau khi nhận, admin theo dõi hệ thống qua Grafana.

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
     └───────────────┴──────── PostgreSQL :5433 (5 database, 5 tài khoản riêng) ──┘

  order-service ──▶ menu-service      (lấy giá món, kiểm tra còn hàng, số phút làm món)
  payment-service ─▶ order-service    (đã thu tiền mặt / ZaloPay ở trạm 1: đưa đơn vào bếp)
  order-service ──▶ payment-service   (kiểm tra đơn đã thanh toán trước khi hủy)
  feedback-service ─▶ order-service   (kiểm tra đơn đã hoàn thành)
  payment-service ─▶ ZaloPay sandbox  (tạo đơn, nhận callback, tra cứu trạng thái)

  prometheus :9090 ──▶ grafana :3000
```

| Service | Cổng | Database | Chức năng |
|---|---|---|---|
| `auth-service` | 8001 | `auth_db` | Đăng ký, đăng nhập, JWT, tài khoản nhân viên trạm và bếp |
| `menu-service` | 8002 | `menu_db` | Cửa hàng, danh mục, món ăn, tình trạng còn/hết món |
| `order-service` | 8003 | `order_db` | Đặt trước, mã nhận món, trạm 1 / bếp / trạm 2, hàng đợi ưu tiên, mã giảm giá |
| `payment-service` | 8004 | `payment_db` | Thanh toán ZaloPay và thu tiền mặt tại trạm 1 |
| `feedback-service` | 8005 | `feedback_db` | Đánh giá 1–5 sao, thống kê theo cửa hàng |
| `gateway` | **8080** | — | Giao diện web và định tuyến API tới các service |
| `prometheus` / `grafana` | 9090 / 3000 | — | Thu thập metrics và dashboard giám sát |

**Nguyên tắc chính:**
- Mỗi service có database riêng **và tài khoản PostgreSQL riêng** (`auth_user`, `menu_user`, `order_user`, `payment_user`, `feedback_user`). Tài khoản của service này bị PostgreSQL từ chối khi vào database của service khác, nên muốn lấy dữ liệu bắt buộc phải gọi API. Kiểm tra bằng `bash scripts/check-db-isolation.sh`.
- Gọi nội bộ giữa các service đi qua `/internal/...`, kèm header `X-Internal-Key`. Gateway chặn mọi đường `/internal/` từ bên ngoài.
- JWT do `auth-service` phát, các service khác tự kiểm tra bằng cùng `JWT_SECRET`.
- Giá tiền luôn tính ở server, không tin giá client gửi lên.

**Vai trò:** khách hàng (`CUSTOMER`), nhân viên trạm 1 / trạm 2 (`STAFF`), bếp (`KITCHEN`), quản trị (`ADMIN`). Nhân viên và bếp gắn với một chi nhánh, chỉ thao tác được đơn của chi nhánh đó.

**Trạng thái đơn hàng:**
```
HOLD ──▶ AWAITING_PAYMENT ──▶ CONFIRMED ──▶ PREPARING ──▶ READY ──▶ COMPLETED
 │        (trạm 1 nhận đơn)   (đã trả tiền,   (bếp làm)   (mời ra    (trạm 2
 │              │               vào bếp)                    trạm 2)    giao)
 └──────────────┴──▶ CANCELLED   (chỉ đơn chưa trả tiền: khách tự hủy hoặc trạm 1 hủy)
```
- **Đặt trước (HOLD):** khách nhập biển số, số điện thoại, chọn tới trong 15 / 30 / 45 phút. Đơn được giữ tới giờ hẹn + 10 phút; quá hạn thì trạm 1 thấy đơn tô đỏ kèm số điện thoại và **tự quyết định hủy**, hệ thống không tự hủy.
- **Trạm 1:** khách đọc mã 4 số (không trùng trong ngày tại chi nhánh), nhân viên nhìn camera đối chiếu biển số (không khớp thì xác minh tên / số điện thoại rồi sửa biển số, có ghi lịch sử). Tiền mặt: nhân viên thu rồi bấm "Đã thu". ZaloPay: khách trả trên điện thoại, callback về thì đơn tự vào bếp.
- **Chỉ thu tiền ở trạm 1** nên đơn chưa vào bếp thì chưa có tiền: hủy không bao giờ phải hoàn tiền. Đã trả tiền thì bếp làm ngay, không hủy được.
- **Bếp:** báo hết món, làm theo hàng đợi, **in phiếu** (mã, biển số, món; khổ 80mm, không có máy in thì "Lưu dưới dạng PDF") dán lên túi rồi bấm "Món đã xong".
- **Trạm 2:** khách đọc mã, nhân viên đối chiếu biển số, bấm "Đã giao".

**Ước lượng giờ xong đơn:**
- Mỗi món có số phút làm cố định (`prep_minutes`, admin sửa trong trang Thực đơn). Mỗi cửa hàng có số đơn bếp làm được cùng lúc (`kitchen_capacity`, sửa trong trang Cửa hàng).
- Thời gian làm 1 đơn = món lâu nhất + 1 phút cho mỗi 2 phần thêm.
- **Thứ tự bếp làm:** đơn đang làm → đơn đã chờ quá 10 phút (ai vào trước làm trước, để đơn lâu không bị chen mãi) → còn lại **đơn làm nhanh trước**. Đơn nhanh xong sớm thì xe rời bãi sớm, thời gian chờ trung bình giảm.
- **Giờ xong dự kiến:** xếp lần lượt các đơn theo thứ tự trên vào `kitchen_capacity` chỗ của bếp, đơn nào cũng lấy chỗ trống sớm nhất. Tính lại mỗi khi hàng đợi thay đổi. Nhiều đơn vào bếp cùng lúc (giờ trưa) được khóa theo chi nhánh (`pg_advisory_xact_lock`) nên không đơn nào bị tính sai.
- Khách thấy "Dự kiến xong lúc …" ở trang đơn; màn hình bếp tô đỏ đơn trễ hẹn. Code: `services/order-service/app/estimate.py`.

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
Script đi hết một vòng: đăng nhập 4 vai trò → đặt trước, nhận mã → trạm 1 thu tiền mặt → bếp làm món → trạm 2 giao → đánh giá → trạm 1 nhận đơn trả ZaloPay → kiểm tra phân quyền và gateway. Cuối cùng in `ĐẠT: 54 bước kiểm tra đều đúng.`

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
| Nhân viên trạm 1 / trạm 2 | `staff1@drivethru.vn` / `staff2@…` / `staff3@…` | 1 Quận 7 / 2 Thủ Đức / 3 Bình Thạnh |
| Bếp | `kitchen1@drivethru.vn` / `kitchen2@…` / `kitchen3@…` | 1 Quận 7 / 2 Thủ Đức / 3 Bình Thạnh |
| Khách hàng | `khachhang@drivethru.vn` | — |

**Kịch bản nên thử** (mở 4 cửa sổ: khách trên điện thoại, nhân viên trạm, bếp, admin):
1. **Khách đặt trước:** chọn cửa hàng → thêm món → nhập biển số, số điện thoại, chọn giờ tới → **Đặt trước và lấy mã**. Trang đơn hiện mã 4 số, giờ hẹn và hạn giữ đơn.
2. **Trạm 1** (`staff1`, tab *Trạm 1*): gõ mã khách đọc (hoặc biển số) → đối chiếu biển số → **Nhận đơn · Tiền mặt** rồi **Thu … · đưa vào bếp** (có ô tính tiền thối). Hoặc **Nhận đơn · ZaloPay**: trang đơn trên điện thoại khách hiện nút thanh toán, trả xong đơn tự vào bếp (xem [mục 5](#5-thanh-toán-zalopay)).
3. **Bếp** (`kitchen1`): hàng đợi xếp đơn nhanh trước, đơn chờ quá 10 phút lên đầu. **In phiếu** (chọn "Lưu dưới dạng PDF" nếu không có máy in) → **Bắt đầu làm** → dán phiếu → **Món đã xong**. Tab *Báo hết món* để bật/tắt món của chi nhánh.
4. **Trạm 2** (`staff1`, tab *Trạm 2*, dùng tốt trên điện thoại): trang khách đổi sang "Mời ra trạm 2". Gõ mã khách đọc hoặc chạm thẻ → đối chiếu biển số → **Đã giao**.
5. **Đánh giá:** khi đơn `COMPLETED`, khách mở lại đơn sẽ thấy ô chấm sao. Đánh giá 1–2 sao bắt buộc ghi lý do.
6. **Hủy đơn:** khách hủy được khi chưa thanh toán ở trạm 1 (không mất tiền). Đơn quá hạn giữ được tô đỏ ở trạm 1 kèm số điện thoại; nhân viên tự quyết định gọi khách hoặc bấm **Hủy đơn**. Đã thanh toán thì bếp làm ngay nên không hủy được.
7. **Admin** (`/admin`): Tổng quan (doanh thu, số đơn, đánh giá theo cửa hàng), Đơn hàng (3 cột Trạm 1 / Bếp / Trạm 2 của mọi chi nhánh), Cửa hàng, Thực đơn, Nhân viên (tạo tài khoản **nhân viên trạm** hoặc **bếp** gắn với chi nhánh), Mã giảm giá, Đánh giá.

---

## 5. Thanh toán ZaloPay

Hệ thống dùng **ZaloPay sandbox** (API v2) với bộ key sandbox công khai (`app_id` 2554), không cần đăng ký tài khoản, không có tiền thật.

**Luồng:**
Khách chỉ trả ZaloPay **khi đã tới trạm 1** và nhân viên đã nhận đơn (đơn ở `AWAITING_PAYMENT`); đơn đang giữ chỗ chưa tạo được giao dịch.

1. Trang đơn trên điện thoại khách gọi `POST /api/payments/zalopay/create` → payment-service gọi API `v2/create` của ZaloPay (ký HMAC-SHA256 bằng `key1`), nhận `order_url` → chuyển khách sang trang ZaloPay.
2. Khách thanh toán trên trang ZaloPay: quét QR bằng app **Zalopay sandbox**, thẻ ATM nội địa hoặc thẻ quốc tế.
3. ZaloPay gọi **callback** `POST /api/payments/zalopay/callback` (server-to-server). payment-service kiểm tra `mac` bằng `key2` và số tiền, rồi báo order-service chuyển đơn sang `CONFIRMED` (vào bếp). Mỗi giao dịch chỉ được xử lý một lần.
4. ZaloPay chuyển khách về `/payment/result`. Web gọi `GET /api/payments/zalopay/return` (kiểm tra `checksum` bằng `key2`, khách không sửa URL để gian lận được). Nếu callback chưa tới, payment-service tự hỏi ZaloPay bằng API `v2/query` có ký, nên **chạy local không có ngrok vẫn xác nhận được đơn**.

**Không phát sinh hoàn tiền.** Tiền chỉ thu ở trạm 1, ngay trước khi đơn vào bếp, nên đơn bị hủy luôn là đơn chưa trả tiền.
- Trước khi hủy một đơn đang chờ trả ZaloPay, order-service gọi `GET /internal/payments/order/{id}/paid?sync=true`. payment-service hỏi lại ZaloPay các giao dịch còn chờ: khách vừa trả xong mà callback chưa tới thì đơn được đưa vào bếp và không bị hủy nhầm.
- Nhân viên vừa đổi sang tiền mặt mà khách đã kịp trả ZaloPay: đơn ghi nhận ZaloPay, trạm 1 không thu tiền lần nữa.

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

Xem database bằng TablePlus/DBeaver: host `localhost`, port `5433` (đổi từ 5432 để không trùng PostgreSQL cài sẵn trên máy), user `admin`, mật khẩu `secretpassword` (giá trị mặc định trong `docker-compose.yml`). Tài khoản `admin` chỉ để quản trị; các service dùng tài khoản riêng (mặc định `auth_user` / `auth_secret`, `menu_user` / `menu_secret`, …).

---

## 7. Chạy test

Có 2 lớp kiểm thử:
- **Test API của từng service** (pytest, 88 test: auth 13 · menu 21 · order 26 · payment 16 · feedback 12): chạy bằng SQLite trong bộ nhớ nên **không cần Postgres hay Docker**. Cần Python 3.12+.
- **Kiểm tra hệ thống thật** (`scripts/smoke_test.py`, 54 bước) và **phân quyền database** (`scripts/check-db-isolation.sh`): chạy với Docker đang bật, xem [mục 3.4](#34-build-và-chạy).

```bash
cd services/payment-service
pip install -r requirements.txt pytest
python -m pytest -q tests
```

| Service | Lệnh (đứng trong thư mục service) | Số test |
|---|---|---|
| `auth-service` | `python -m pytest -q test_auth.py` | 12 |
| `services/menu-service` | `python -m pytest -q tests` | 20 |
| `services/order-service` | `python -m pytest -q tests` | 24 |
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
| `port is already allocated` / TablePlus báo sai mật khẩu `admin` | Máy đang có Postgres cài sẵn. Postgres của Docker đã mở ở cổng **5433** (`docker-compose.yml`); kết nối TablePlus vào `localhost:5433` |
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

**Sao không thu tiền ngay khi đặt trên web?**
Tiền chỉ thu ở trạm 1, khi khách đã có mặt, rồi đơn mới vào bếp. Nhờ vậy món không bị làm sẵn rồi nguội khi khách tới trễ, cửa hàng không mất nguyên liệu cho đơn khách bỏ, và hủy đơn không bao giờ phải hoàn tiền.

**Xe tới mà món chưa xong thì có làm kẹt làn không?**
Không. Sau trạm 1 xe vào bãi chờ; chỉ khi bếp bấm "Món đã xong" khách mới được mời ra trạm 2, nên trạm 2 lúc nào cũng giao được ngay.

**Bếp làm đơn theo thứ tự nào?**
Đơn làm nhanh trước để giảm thời gian chờ trung bình; đơn đã chờ quá 10 phút được đẩy lên đầu để không bị chen mãi. Giờ dự kiến của mọi đơn được tính lại theo đúng thứ tự này.
