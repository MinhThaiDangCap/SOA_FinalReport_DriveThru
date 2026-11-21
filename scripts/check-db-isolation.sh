#!/bin/bash
# Kiểm tra mỗi service chỉ vào được database của chính nó (database-per-service).
# Thử đăng nhập 5 tài khoản service vào cả 5 database: đúng cặp phải VÀO ĐƯỢC,
# mọi cặp khác phải bị PostgreSQL từ chối (permission denied).
#
# Chạy khi hệ thống đang bật:  bash scripts/check-db-isolation.sh
set -uo pipefail

CONTAINER="${POSTGRES_CONTAINER:-drivethru_postgres}"
SERVICES=(auth menu order payment feedback)

# Bên trong container, kết nối qua socket nội bộ nên không cần mật khẩu.
# Quyền CONNECT vẫn được kiểm tra bình thường.
can_connect() {
  docker exec "$CONTAINER" psql -U "$1" -d "$2" -tAc "SELECT 1" >/dev/null 2>&1
}

# In chuỗi rồi thêm khoảng trắng cho đủ $2 ký tự (printf đếm byte nên lệch với tiếng Việt)
pad() {
  local text="$1" width="$2"
  printf '%s%*s' "$text" $(( width > ${#text} ? width - ${#text} : 1 )) ''
}

if ! docker exec "$CONTAINER" true 2>/dev/null; then
  echo "Không thấy container $CONTAINER. Hãy chạy: docker compose up -d" >&2
  exit 2
fi

pad "tài khoản \\ db" 16
for db in "${SERVICES[@]}"; do pad "${db}_db" 13; done
echo

failed=0
for svc in "${SERVICES[@]}"; do
  user="${svc}_user"
  pad "$user" 16
  for db in "${SERVICES[@]}"; do
    if can_connect "$user" "${db}_db"; then ok=1; else ok=0; fi
    if [[ "$svc" == "$db" ]]; then
      if (( ok )); then cell="✔ vào được"; else cell="✘ LỖI"; failed=1; fi
    else
      if (( ok )); then cell="✘ LỌT"; failed=1; else cell="· bị chặn"; fi
    fi
    pad "$cell" 13
  done
  echo
done

echo
if (( failed )); then
  echo "KHÔNG ĐẠT: có service vào được database không phải của mình (hoặc không vào được database của mình)."
  echo "Nếu database được tạo từ bản cũ, chạy: docker compose down -v && docker compose up -d --build"
  exit 1
fi
echo "ĐẠT: mỗi service chỉ truy cập được database của chính nó."
