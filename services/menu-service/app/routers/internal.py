from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuItem, Station
from app.routers.stations import unavailable_item_ids
from app.schemas import InternalItemOut, StationOut
from app.security import verify_internal_key

# Các endpoint này KHÔNG mở qua Nginx gateway, chỉ service khác gọi trong mạng Docker.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_key)],
)


@router.get("/items", response_model=list[InternalItemOut])
def get_items_for_order(
    station_id: int,
    ids: str = Query(description="Danh sách id món, cách nhau bằng dấu phẩy: 1,2,3"),
    db: Session = Depends(get_db),
):
    """order-service gọi khi tạo đơn để lấy tên, giá và tình trạng còn/hết.

    Món không tồn tại, đã ngừng bán, hoặc cửa hàng không hoạt động thì
    không có trong kết quả.
    """
    try:
        item_ids = {int(x) for x in ids.split(",") if x.strip()}
    except ValueError:
        raise HTTPException(status_code=400, detail="ids phải là các số nguyên")

    station = db.get(Station, station_id)
    if station is None or not station.is_active or not item_ids:
        return []

    sold_out = unavailable_item_ids(db, station_id)
    items = db.scalars(
        select(MenuItem).where(
            MenuItem.id.in_(item_ids), MenuItem.is_active.is_(True)
        )
    ).all()
    return [
        InternalItemOut(
            id=it.id, name=it.name, price=it.price, available=it.id not in sold_out
        )
        for it in items
    ]


@router.get("/stations/{station_id}", response_model=StationOut)
def get_station_internal(station_id: int, db: Session = Depends(get_db)):
    """Cho service khác kiểm tra cửa hàng có tồn tại không."""
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cửa hàng")
    return station
