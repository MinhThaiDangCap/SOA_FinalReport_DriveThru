import time

import httpx
from fastapi import HTTPException

from app import config

# Món giả dùng khi MENU_MOCK=true (id 4 cố ý để "hết hàng" để test lỗi)
MOCK_ITEMS = {
    1: {"id": 1, "name": "Burger bò", "price": 45000, "available": True, "prep_minutes": 5},
    2: {"id": 2, "name": "Khoai tây chiên", "price": 25000, "available": True, "prep_minutes": 3},
    3: {"id": 3, "name": "Coca-Cola", "price": 15000, "available": True, "prep_minutes": 2},
    4: {"id": 4, "name": "Gà rán (hết)", "price": 60000, "available": False, "prep_minutes": 7},
}


def get_kitchen_capacities() -> dict[int, int]:
    """{station_id: số đơn bếp làm cùng lúc}. Chỉ dùng để ước lượng thời gian,
    nên menu-service lỗi thì trả {} (dùng giá trị mặc định) chứ không báo lỗi."""
    if config.MENU_MOCK:
        return {}
    try:
        resp = httpx.get(
            f"{config.MENU_SERVICE_URL}/internal/stations",
            headers={"X-Internal-Key": config.INTERNAL_KEY},
            timeout=2.0,
        )
        resp.raise_for_status()
        return {s["id"]: s.get("kitchen_capacity", 2) for s in resp.json()}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {}


def get_menu_items(station_id: int, item_ids: list[int]) -> dict[int, dict]:
    """Trả về {item_id: {"id", "name", "price", "available"}}.

    Món không tồn tại ở cửa hàng này thì không có trong kết quả.
    """
    if config.MENU_MOCK:
        return {i: MOCK_ITEMS[i] for i in item_ids if i in MOCK_ITEMS}

    url = f"{config.MENU_SERVICE_URL}/internal/items"
    params = {"ids": ",".join(map(str, item_ids)), "station_id": station_id}
    headers = {"X-Internal-Key": config.INTERNAL_KEY}

    for attempt in range(3):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=3.0)
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"menu-service lỗi {resp.status_code}")
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail="Menu service từ chối yêu cầu từ order-service",
                )
            return {item["id"]: item for item in resp.json()}
        except httpx.HTTPError:
            if attempt < 2:
                time.sleep(0.3)

    raise HTTPException(
        status_code=503,
        detail="Menu service không phản hồi, vui lòng thử lại sau",
    )