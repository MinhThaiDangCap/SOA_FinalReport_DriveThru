"""Dữ liệu mẫu, chỉ thêm khi database còn trống.

Bốn món đầu (id 1-4) trùng với MOCK_ITEMS trong order-service/app/menu_client.py
để order-service chuyển từ MENU_MOCK=true sang gọi thật mà không phải đổi id.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, MenuItem, Station, StationItemAvailability

STATIONS = [
    ("Drive-Thru Quận 7", "19 Nguyễn Hữu Thọ, P. Tân Phong, Quận 7, TP.HCM", "06:00 - 23:00"),
    ("Drive-Thru Thủ Đức", "720A Xa lộ Hà Nội, TP. Thủ Đức, TP.HCM", "06:00 - 22:00"),
    ("Drive-Thru Bình Thạnh", "208 Điện Biên Phủ, Quận Bình Thạnh, TP.HCM", "24/7"),
]

CATEGORIES = ["Burger", "Gà rán", "Món ăn kèm", "Đồ uống", "Tráng miệng"]

# (danh mục, tên, mô tả, giá VND) — thứ tự quyết định id
ITEMS = [
    ("Burger", "Burger bò", "Bò nướng, phô mai, rau tươi, sốt đặc biệt", 45000),
    ("Món ăn kèm", "Khoai tây chiên", "Khoai chiên giòn, cỡ vừa", 25000),
    ("Đồ uống", "Coca-Cola", "Ly 500ml, có đá", 15000),
    ("Gà rán", "Gà rán", "2 miếng gà giòn cay", 60000),
    ("Burger", "Burger gà giòn", "Gà chiên giòn, xà lách, sốt mayonnaise", 42000),
    ("Burger", "Burger phô mai đôi", "Hai lớp bò, hai lớp phô mai", 65000),
    ("Burger", "Burger tôm", "Nhân tôm chiên xù, sốt tartar", 49000),
    ("Gà rán", "Gà viên", "6 viên gà kèm sốt chấm", 35000),
    ("Gà rán", "Cánh gà sốt cay", "4 cánh gà phủ sốt cay Hàn Quốc", 55000),
    ("Món ăn kèm", "Salad bắp cải", "Bắp cải trộn sốt kem", 20000),
    ("Món ăn kèm", "Khoai tây nghiền", "Khoai nghiền kèm sốt nâu", 22000),
    ("Đồ uống", "Trà đào", "Trà đào cam sả, ly 500ml", 29000),
    ("Đồ uống", "Cà phê sữa đá", "Cà phê phin pha sẵn", 25000),
    ("Đồ uống", "Nước suối", "Chai 500ml", 10000),
    ("Tráng miệng", "Kem vani", "Kem tươi ốc quế", 12000),
    ("Tráng miệng", "Bánh táo", "Bánh nhân táo quế nướng", 18000),
]

# (station_id, item_id) đang hết hàng — để có sẵn trạng thái "hết" khi demo
SOLD_OUT = [(1, 4), (2, 15)]


def seed_if_empty(db: Session) -> bool:
    """Trả về True nếu đã thêm dữ liệu mẫu."""
    if db.scalar(select(Station.id).limit(1)) is not None:
        return False

    for name, address, hours in STATIONS:
        db.add(Station(name=name, address=address, opening_hours=hours))

    categories = {}
    for order, name in enumerate(CATEGORIES, start=1):
        categories[name] = Category(name=name, sort_order=order)
        db.add(categories[name])
    db.flush()

    # flush từng món để id tăng đúng theo thứ tự trong ITEMS
    for cat_name, name, description, price in ITEMS:
        db.add(
            MenuItem(
                category_id=categories[cat_name].id,
                name=name,
                description=description,
                price=price,
            )
        )
        db.flush()

    for station_id, item_id in SOLD_OUT:
        db.add(
            StationItemAvailability(
                station_id=station_id, item_id=item_id, is_available=False
            )
        )

    db.commit()
    return True
