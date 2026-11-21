#!/bin/bash
# Chạy MỘT LẦN khi PostgreSQL khởi tạo lần đầu (volume pgdata còn trống).
#
# Database-per-service: mỗi service có tài khoản PostgreSQL riêng và chỉ vào được
# database của chính nó. Tài khoản quản trị (POSTGRES_USER) chỉ dùng để quản trị,
# xem dữ liệu bằng TablePlus; các service không dùng tài khoản này.
#
# Kiểm tra: scripts/check-db-isolation.sh
# Không dùng "set -u": khi file không có quyền chạy, entrypoint của image postgres
# "source" file này, đổi chế độ shell có thể làm hỏng phần còn lại của entrypoint.

create_service_db() {
  local db="$1" user="$2" password="$3"
  # Dùng biến psql (:'x') và format(%I, %L) để tên và mật khẩu được trích dẫn an toàn
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v db="$db" -v usr="$user" -v pw="$password" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'usr', :'pw') \gexec
-- Service là chủ database: tự tạo và sửa bảng của mình
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'usr') \gexec
-- Mặc định mọi tài khoản đều được CONNECT vào mọi database: thu hồi quyền đó
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'db') \gexec
SQL
  echo "Đã tạo database $db, chỉ tài khoản $user được truy cập"
}

create_service_db auth_db     auth_user     "${AUTH_DB_PASSWORD:-auth_secret}"
create_service_db menu_db     menu_user     "${MENU_DB_PASSWORD:-menu_secret}"
create_service_db order_db    order_user    "${ORDER_DB_PASSWORD:-order_secret}"
create_service_db payment_db  payment_user  "${PAYMENT_DB_PASSWORD:-payment_secret}"
create_service_db feedback_db feedback_user "${FEEDBACK_DB_PASSWORD:-feedback_secret}"
