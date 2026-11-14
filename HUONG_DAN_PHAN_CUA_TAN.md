# 📘 TÀI LIỆU HƯỚNG DẪN & BÁO CÁO PHẦN CỦA TÂN (THÀNH VIÊN C)

Tài liệu này tổng hợp toàn bộ phần công việc của **Tân (Người C)** trong đồ án **Hệ thống Đặt món Drive-Thru (Kiến trúc Microservices - 504070)**, bao gồm:
1. **`auth-service`** (Xác thực, Phân quyền JWT, Quản lý Nhân viên, Liên kết Telegram).
2. **`feeback-service`** (Đánh giá dịch vụ 1–5 sao, Kiểm tra đơn hàng, Thống kê Admin, Đồng bộ Telegram).
3. **`telegram-bot` & `notification-service`** (Tích hợp từ dự án Seminar: Nhận `/start <token>`, gửi thông báo trạng thái đơn, gửi khảo sát 5 sao và lưu thẳng vào `feedback_db`).
4. **Giám sát hệ thống (`Prometheus` + `Grafana`)** (Tự động thu thập `/metrics` và dựng sẵn Dashboard 6 biểu đồ).
5. **Giao diện Frontend (`Dashboard Nhân viên & Admin`)** (React + Vite).

---

## 1. Sơ Đồ Các Thành Phần Tân Đảm Nhận

| Thành phần | Cổng (Port) | Database sở hữu | Bảng dữ liệu (Xem trên TablePlus) |
| :--- | :---: | :---: | :--- |
| **`auth-service`** | `8001` | `auth_db` | `users`, `refresh_tokens` |
| **`feeback-service`** | `8002` | `feedback_db` | `reviews` |
| **`notification-service`** | `8006` | *(Stateless)* | Gửi thông báo & khảo sát qua Telegram API |
| **`telegram-bot` (Java)** | *(Polling)* | *(Gọi REST)* | Nhận `/start <token>` và phiếu khảo sát 5 sao |
| **`prometheus`** | `9090` | *(Time-series)* | Thu thập `/metrics` mỗi 15 giây |
| **`grafana`** | `3000` | *(Provisioned)* | Dashboard tự động nạp sẵn |
| **`frontend`** | `5173` | — | Giao diện Nhân viên, Admin, Khách hàng |

---

## 2. Thông Tin Kết Nối TablePlus (Xem Database)

Container PostgreSQL (`drivethru_postgres`) đã chạy và tạo sẵn đủ 5 database (`auth_db`, `feedback_db`, `menu_db`, `order_db`, `payment_db`):

- **Host**: `localhost` (hoặc `127.0.0.1`)
- **Port**: `5432`
- **User**: `admin`
- **Password**: `secretpassword`
- **Database**: Gõ `auth_db` hoặc `feedback_db`

### Các tài khoản mẫu tự động tạo sẵn trong `auth_db` (Bảng `users`):
| Vai trò | Email | Mật khẩu | Trạm (`station_id`) |
| :--- | :--- | :--- | :---: |
| **Admin** | `admin@drivethru.vn` | `Password123` | `NULL` (Toàn hệ thống) |
| **Nhân viên Trạm 1** | `staff1@drivethru.vn` | `Password123` | `1` (CN Quận 1) |
| **Nhân viên Trạm 2** | `staff2@drivethru.vn` | `Password123` | `2` (CN Quận 7) |
| **Khách hàng** | `khachhang@drivethru.vn` | `Password123` | `NULL` |

---

## 3. Cách Chạy Hệ Thống Để Code & Demo

### Cách A: Chạy tất cả bằng 1 lệnh Docker Compose (Khuyên dùng khi Demo)
Tại thư mục gốc `SOA_FinalReport_DriveThru`, mở Terminal chạy:
```powershell
docker compose up -d --build
```
Sau khi chạy xong, mở trình duyệt tại:
- **Swagger Auth Service**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Swagger Feedback Service**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **Swagger Notification Service**: [http://localhost:8006/docs](http://localhost:8006/docs)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000) (Đăng nhập: `admin` / `admin` → Vào mục **Dashboards** → Mở **Drive-Thru Microservices & Business Monitoring**)

### Cách B: Chạy Giao diện Frontend (React + Vite)
Mở 1 Terminal mới:
```powershell
cd frontend
npm install
npm run dev
```
👉 Mở trình duyệt tại: **[http://localhost:5173](http://localhost:5173)**

---

