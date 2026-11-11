# menu-service

Quản lý cửa hàng (station), danh mục, món và tình trạng còn/hết theo từng cửa hàng.
Database riêng: `menu_db`. Qua gateway: `/api/menu`.

## Chạy khi dev

```bash
cd services/menu-service
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Chưa có Postgres thì dùng SQLite (PowerShell):

```powershell
$env:DATABASE_URL = "sqlite:///./menu_dev.db"
uvicorn app.main:app --reload --port 8002
```

Có Postgres thì bỏ `DATABASE_URL`, service đọc `POSTGRES_*` và `MENU_DB` từ `.env`
(database `menu_db` phải được tạo trước).

- Swagger: http://localhost:8002/docs
- Lần chạy đầu, nếu database trống, service tự thêm 3 cửa hàng, 5 danh mục, 16 món mẫu
  (tắt bằng `SEED_DATA=false`).

## Test

```bash
pytest
```

Test dùng SQLite trong RAM, không cần Postgres.

## API

Lỗi luôn trả dạng `{"detail": "..."}`. Giá là VND, số nguyên.

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/menu/stations` | công khai | Cửa hàng đang hoạt động |
| GET | `/api/menu/stations/all` | ADMIN | Mọi cửa hàng, kể cả đã ngừng |
| GET | `/api/menu/stations/{id}` | công khai | Một cửa hàng |
| GET | `/api/menu/stations/{id}/menu` | công khai | Menu gom theo danh mục, kèm `available` |
| PUT | `/api/menu/stations/{id}/items/{item_id}/availability` | STAFF (đúng cửa hàng), ADMIN | Báo còn/hết: `{"available": false}` |
| POST / PUT / DELETE | `/api/menu/stations[/{id}]` | ADMIN | Quản lý cửa hàng (DELETE là xóa mềm) |
| GET | `/api/menu/categories` | công khai | Danh mục |
| POST / PUT / DELETE | `/api/menu/categories[/{id}]` | ADMIN | Quản lý danh mục (còn món thì không xóa được) |
| GET | `/api/menu/items`, `/api/menu/items/{id}` | công khai | Món (không gắn cửa hàng) |
| POST / PUT / DELETE | `/api/menu/items[/{id}]` | ADMIN | Quản lý món (DELETE là xóa mềm) |
| GET | `/internal/items?station_id=1&ids=1,2,3` | `X-Internal-Key` | order-service lấy tên, giá, còn/hết |
| GET | `/internal/stations/{id}` | `X-Internal-Key` | Kiểm tra cửa hàng tồn tại |
| GET | `/health`, `/metrics`, `/docs` | công khai | Hệ thống |

Ví dụ `GET /api/menu/stations/1/menu`:

```json
{
  "station": {"id": 1, "name": "Drive-Thru Quận 7", "address": "...", "opening_hours": "06:00 - 23:00", "is_active": true},
  "categories": [
    {"id": 1, "name": "Burger", "items": [
      {"id": 1, "name": "Burger bò", "description": "...", "price": 45000, "image_url": null, "available": true}
    ]}
  ]
}
```

## Quy tắc nghiệp vụ

- Mọi món đang bán (`is_active`) có ở mọi cửa hàng. Bảng `station_item_availability`
  chỉ ghi lại món nào đang **hết** ở cửa hàng nào; không có dòng nghĩa là còn.
- `/internal/items` bỏ qua món không tồn tại, món đã ngừng bán, và trả `[]` nếu cửa hàng
  không tồn tại hoặc đã ngừng hoạt động.
- Id món mẫu 1–4 trùng với `MOCK_ITEMS` của order-service, nên order-service chỉ cần đặt
  `MENU_MOCK=false` là chuyển sang gọi thật.
- Nginx gateway chỉ được mở `/api/menu/`, **không** mở `/internal/`.

## Metric nghiệp vụ

`menu_availability_changes_total{available="true|false"}`: số lần đổi tình trạng còn/hết.
