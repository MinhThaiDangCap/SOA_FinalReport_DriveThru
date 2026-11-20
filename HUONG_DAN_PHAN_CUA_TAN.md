# 📘 TÀI LIỆU HƯỚNG DẪN & BÁO CÁO PHẦN CỦA TÂN (THÀNH VIÊN C)

Tài liệu này tổng hợp toàn bộ phần công việc của **Tân (Người C)** trong đồ án **Hệ thống Đặt món Drive-Thru GoLane (Kiến trúc Microservices - 504070)**, bao gồm:
1. **`auth-service`** (Xác thực, Phân quyền JWT, Quản lý Nhân viên).
2. **`feeback-service`** (Đánh giá dịch vụ 1–5 sao, Kiểm tra đơn hàng với `order-service`, Thống kê Admin).
3. **Giám sát hệ thống (`Prometheus` + `Grafana`)** (Tự động thu thập `/metrics` từ toàn bộ 5 microservices và dựng sẵn Dashboard 6 biểu đồ).
4. **Giao diện Frontend (`Màn hình Quầy Nhân viên & Trang Quản trị Admin`)** (React + Vite).

---

## 1. Sơ Đồ Các Thành Phần Tân Đảm Nhận

| Thành phần | Cổng (Port) | Database sở hữu | Bảng dữ liệu (Xem trên TablePlus) |
| :--- | :---: | :---: | :--- |
| **`auth-service`** | `8001` | `auth_db` | `users`, `refresh_tokens` |
| **`feeback-service`** | `8005` | `feedback_db` | `reviews` |
| **`prometheus`** | `9090` | *(Time-series)* | Thu thập `/metrics` mỗi 15 giây |
| **`grafana`** | `3000` | *(Provisioned)* | Dashboard tự động nạp sẵn |
| **`gateway` (Frontend)** | `8080` | — | Giao diện Khách hàng, Nhân viên (`/staff`), Admin (`/admin`) |

---

## 2. Thông Tin Kết Nối TablePlus (Xem Database)

Container PostgreSQL (`drivethru_postgres`) chạy trên cổng `5432` với đủ 5 database (`auth_db`, `feedback_db`, `menu_db`, `order_db`, `payment_db`):

- **Host**: `localhost` (hoặc `127.0.0.1`)
- **Port**: `5432`
- **User**: `admin`
- **Password**: `secretpassword`
- **Database**: Gõ `auth_db` hoặc `feedback_db`

### Các tài khoản mẫu tự động tạo sẵn trong `auth_db` (Bảng `users`):
| Vai trò | Email | Mật khẩu | Trạm (`station_id`) |
| :--- | :--- | :--- | :---: |
| **ADMIN** | `admin@drivethru.vn` | `Password123` | `NULL` (Toàn hệ thống) |
| **STAFF (Trạm 1)** | `staff1@drivethru.vn` | `Password123` | `1` (GoLane Quận 7) |
| **STAFF (Trạm 2)** | `staff2@drivethru.vn` | `Password123` | `2` (GoLane Thủ Đức) |
| **STAFF (Trạm 3)** | `staff3@drivethru.vn` | `Password123` | `3` (GoLane Bình Thạnh) |
| **CUSTOMER** | `khachhang@drivethru.vn` | `Password123` | `NULL` |

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
