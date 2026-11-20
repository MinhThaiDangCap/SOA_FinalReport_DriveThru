# 📘 TÀI LIỆU HƯỚNG DẪN & BÁO CÁO PHẦN CỦA TÂN (THÀNH VIÊN C)

Tài liệu này tổng hợp toàn bộ phần công việc của **Tân (Người C)** trong đồ án **Hệ thống Đặt món Drive-Thru GoLane (Kiến trúc Microservices - 504070)**, bao gồm:
1. **`auth-service`** (Xác thực, Phân quyền JWT, Quản lý Nhân viên).
2. **`feeback-service`** (Đánh giá dịch vụ 1–5 sao, Kiểm tra đơn hàng với `order-service`, Thống kê Admin).
3. **Giám sát hệ thống (`Prometheus` + `Grafana`)** (Tự động thu thập `/metrics` từ toàn bộ 5 microservices và dựng sẵn Dashboard 6 biểu đồ).
4. **Giao diện Frontend (`Màn hình Quầy Nhân viên & Trang Quản trị Admin`)** (React + Vite).

---

## 1. Sơ Đồ Các Thành Phần Tân Đảm Nhận

| Thành phần               | Cổng (Port) | Database sở hữu | Bảng dữ liệu (Xem trên TablePlus)                            |
| :----------------------- | :---------: | :-------------: | :----------------------------------------------------------- |
| **`auth-service`**       |   `8001`    |    `auth_db`    | `users`, `refresh_tokens`                                    |
| **`feeback-service`**    |   `8005`    |  `feedback_db`  | `reviews`                                                    |
| **`prometheus`**         |   `9090`    | _(Time-series)_ | Thu thập `/metrics` mỗi 15 giây                              |
| **`grafana`**            |   `3000`    | _(Provisioned)_ | Dashboard tự động nạp sẵn                                    |
| **`gateway` (Frontend)** |   `8080`    |        —        | Giao diện Khách hàng, Nhân viên (`/staff`), Admin (`/admin`) |

---

## 2. Thông Tin Kết Nối TablePlus (Xem Database)

Container PostgreSQL (`drivethru_postgres`) chạy trên cổng `5432` với đủ 5 database (`auth_db`, `feedback_db`, `menu_db`, `order_db`, `payment_db`):

- **Host**: `localhost` (hoặc `127.0.0.1`)
- **Port**: `5432`
- **User**: `admin`
- **Password**: `secretpassword`
- **Database**: Gõ `auth_db` hoặc `feedback_db`

### Các tài khoản mẫu tự động tạo sẵn trong `auth_db` (Bảng `users`):

| Vai trò            | Email                    | Mật khẩu      |   Trạm (`station_id`)   |
| :----------------- | :----------------------- | :------------ | :---------------------: |
| **ADMIN**          | `admin@drivethru.vn`     | `Password123` | `NULL` (Toàn hệ thống)  |
| **STAFF (Trạm 1)** | `staff1@drivethru.vn`    | `Password123` |   `1` (GoLane Quận 7)   |
| **STAFF (Trạm 2)** | `staff2@drivethru.vn`    | `Password123` |  `2` (GoLane Thủ Đức)   |
| **STAFF (Trạm 3)** | `staff3@drivethru.vn`    | `Password123` | `3` (GoLane Bình Thạnh) |
| **CUSTOMER**       | `khachhang@drivethru.vn` | `Password123` |         `NULL`          |

---

## 3. Cách Chạy Hệ Thống Để Code & Demo

Tại thư mục gốc `SOA_FinalReport_DriveThru`, mở Terminal chạy:

```powershell
docker compose up -d --build
```

Sau khi chạy xong, mở trình duyệt tại:

- **Giao diện Web GoLane (Qua Gateway Nginx)**: [http://localhost:8080](http://localhost:8080)
- **Swagger Auth Service**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Swagger Feedback Service**: [http://localhost:8005/docs](http://localhost:8005/docs)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000) (Đăng nhập: `admin` / `admin` → Vào mục **Dashboards** → Mở **Drive-Thru Microservices & Business Monitoring**)

---

## 4. Điểm Nhấn Kỹ Thuật Để Trả Lời Vấn Đáp (Ăn Điểm 9–10)

1. **Vì sao các service khác biết user là ai mà không cần hỏi lại `auth-service` mỗi request?**
   - Vì `auth-service` ký **JWT (Stateless Authentication)** bằng thuật toán `HS256` kèm payload (`sub`, `email`, `role`, `station_id`). Các service khác (`feeback-service`, `order-service`, `menu-service`, `payment-service`) chỉ cần dùng chung `JWT_SECRET` để kiểm tra chữ ký số, giúp giảm tải mạng nội bộ và không tạo điểm nghẽn (Single Point of Failure).
2. **`feeback-service` kiểm soát tính toàn vẹn dữ liệu như thế nào khi không có khóa ngoại (Foreign Key) sang `order_db`?**
   - Áp dụng mẫu **Database-per-Service**: `reviews.order_id` và `reviews.customer_id` là các ID tham chiếu logic. Khi khách gửi đánh giá, `feeback-service` gọi REST đồng bộ sang `order-service` (`/internal/orders/{id}` kèm header `X-Internal-Key`, có timeout 3 giây và retry 2 lần) để xác minh đơn hàng đã `COMPLETED` và đúng chủ sở hữu.
3. **Khi khách chấm 1–2 sao thì điều gì xảy ra?**
   - Pydantic Schema (`@model_validator`) chặn ngay nếu khách không nhập lý do (`HTTP 422`), đồng thời bộ đếm metric `negative_reviews_total` trên Prometheus/Grafana tăng lên theo từng cửa hàng để Admin kịp thời chấn chỉnh chất lượng phục vụ.

   ## 6. Lưu ý khi chạy local

- `MOMO_PROCESS_ON_RETURN=true` (mặc định): MoMo không gọi IPN vào `localhost` được, nên trang kết quả tự xác nhận giao dịch (vẫn kiểm tra chữ ký).
- `MOMO_REDIRECT_URL` mặc định trong Docker là `http://localhost:8080/payment/result`.
- Muốn MoMo gọi IPN thật: dùng ngrok, xem mục 7 bên dưới.
- Mất mạng khi demo: đặt `PAYMENT_MOCK_MODE=true` để dùng thanh toán giả.
- Xem log khi lỗi: `docker compose logs -f payment-service`

---

## 7. Chạy với ngrok (cho MoMo gọi IPN thật)

Chỉ cần khi demo hoặc khi muốn kiểm tra IPN. Chạy bình thường ở local thì bỏ qua mục này.

### 7.1 Chuẩn bị (mỗi người làm cho máy của mình)
1. Tạo tài khoản miễn phí tại https://ngrok.com.
2. Vào dashboard → **Your Authtoken** để lấy authtoken.
3. Vào mục **Domains** để lấy domain miễn phí dạng `xxxx.ngrok-free.app` (hoặc `.ngrok-free.dev`). Nếu chưa có thì tạo mới.

> Mỗi người dùng **token và domain của chính mình**. Một domain không chạy online ở hai máy cùng lúc (lỗi `ERR_NGROK_334`).
> Không đưa token vào bất kỳ file nào được push lên GitHub.

### 7.2 Cấu hình `.env`
Chỉ ghi domain, không có `https://` và không có dấu `/` ở cuối:

```
NGROK_AUTHTOKEN=<token của bạn>
NGROK_DOMAIN=<domain của bạn>
MOMO_IPN_URL=https://<domain của bạn>/api/payments/momo/ipn
MOMO_REDIRECT_URL=https://<domain của bạn>/payment/result
```

Dòng `MOMO_REDIRECT_URL` cũ (`http://localhost:8080/payment/result`) nên đặt dấu `#` ở đầu để quay lại sau demo.

### 7.3 Chạy
```bash
docker compose --profile tunnel up -d ngrok
docker compose up -d payment-service
```

Kiểm tra:
```bash
docker logs drivethru_ngrok --tail 20
docker compose exec payment-service printenv MOMO_IPN_URL MOMO_REDIRECT_URL
```
- Log ngrok phải báo tunnel online với đúng domain của bạn.
- Nếu log báo `unknown flag: --url`, đổi `--url=` thành `--domain=` ở lệnh `command` của service `ngrok` trong `docker-compose.yml`.
- `printenv` phải in ra hai URL bắt đầu bằng `https://<domain của bạn>`.

### 7.4 Kiểm tra
1. Mở `https://<domain của bạn>/` trên trình duyệt. Nếu hiện trang cảnh báo của ngrok thì bấm **Visit Site**. Web phải hiện ra.
2. Mở http://localhost:4040 để xem request đi qua tunnel.
3. Tự gửi một IPN giả. Trên Windows PowerShell gõ `curl.exe` (có đuôi `.exe`):
   ```powershell
   curl.exe -i -X POST https://<domain của bạn>/api/payments/momo/ipn -H "Content-Type: application/json" -d "{}"
   ```
   Dòng đầu của kết quả là `HTTP/1.1 204 No Content`. Body này không có chữ ký hợp lệ nên hệ thống bỏ qua, không đổi trạng thái đơn nào.
4. Đặt một đơn MoMo qua **chính link ngrok** (đăng nhập ngay trên link đó, vì đăng nhập ở `localhost:8080` không dùng chung được). Sau khi thanh toán, ở trang 4040 lọc chữ `ipn`, nếu thấy `POST /api/payments/momo/ipn` mã `204` là MoMo đã gọi IPN thật. IPN có thể đến chậm vài giây, và sandbox đôi khi không gửi.

### 7.5 Lưu ý
- Mở link `/api/payments/momo/ipn` bằng trình duyệt sẽ ra `405 Method Not Allowed`. Bình thường, vì route này chỉ nhận POST.
- Khi tunnel đang bật, ai có link cũng vào được hệ thống của bạn. Gateway đã chặn `/internal/` và `/metrics`, nhưng vẫn nên tắt sau khi dùng:
  ```bash
  docker compose --profile tunnel stop ngrok
  ```
- Tắt tunnel xong thì đặt lại `MOMO_REDIRECT_URL=http://localhost:8080/payment/result`, rồi chạy `docker compose up -d payment-service`. Nếu để nguyên link ngrok thì thanh toán ở local sẽ bị chuyển về trang không mở được.
- Nếu không muốn dựng tunnel riêng, hãy xin nhóm trưởng gửi link ngrok qua chat riêng. Khi máy nhóm trưởng đang chạy Docker và tunnel, link đó dùng được mà không cần token.
