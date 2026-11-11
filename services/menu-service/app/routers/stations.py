from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, MenuItem, Station, StationItemAvailability
from app.schemas import (
    AvailabilityIn,
    AvailabilityOut,
    StationIn,
    StationMenuCategory,
    StationMenuItem,
    StationMenuOut,
    StationOut,
)
from app.security import require_roles

router = APIRouter(prefix="/api/menu/stations", tags=["stations"])

AVAILABILITY_CHANGES = Counter(
    "menu_availability_changes_total",
    "Số lần nhân viên đổi tình trạng còn/hết của món",
    ["available"],
)


def _get_station(db: Session, station_id: int) -> Station:
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cửa hàng")
    return station


def unavailable_item_ids(db: Session, station_id: int) -> set[int]:
    """Id các món đang bị báo hết tại cửa hàng."""
    rows = db.scalars(
        select(StationItemAvailability.item_id).where(
            StationItemAvailability.station_id == station_id,
            StationItemAvailability.is_available.is_(False),
        )
    )
    return set(rows)


# ---------- Khách xem (không cần đăng nhập) ----------
@router.get("", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db)):
    """Danh sách cửa hàng đang hoạt động."""
    return db.scalars(
        select(Station).where(Station.is_active.is_(True)).order_by(Station.id)
    ).all()


@router.get("/all", response_model=list[StationOut])
def list_all_stations(
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    """Admin: mọi cửa hàng, kể cả đã ngừng hoạt động."""
    return db.scalars(select(Station).order_by(Station.id)).all()


@router.get("/{station_id}", response_model=StationOut)
def get_station(station_id: int, db: Session = Depends(get_db)):
    return _get_station(db, station_id)


@router.get("/{station_id}/menu", response_model=StationMenuOut)
def get_station_menu(station_id: int, db: Session = Depends(get_db)):
    """Menu của một cửa hàng, gom theo danh mục, kèm tình trạng còn/hết."""
    station = _get_station(db, station_id)
    if not station.is_active:
        raise HTTPException(status_code=404, detail="Cửa hàng đã ngừng hoạt động")

    sold_out = unavailable_item_ids(db, station_id)
    items = db.scalars(
        select(MenuItem).where(MenuItem.is_active.is_(True)).order_by(MenuItem.id)
    ).all()
    categories = db.scalars(
        select(Category).order_by(Category.sort_order, Category.id)
    ).all()

    result = []
    for cat in categories:
        cat_items = [
            StationMenuItem(
                id=it.id,
                name=it.name,
                description=it.description,
                price=it.price,
                image_url=it.image_url,
                available=it.id not in sold_out,
            )
            for it in items
            if it.category_id == cat.id
        ]
        if cat_items:  # bỏ danh mục rỗng
            result.append(
                StationMenuCategory(id=cat.id, name=cat.name, items=cat_items)
            )

    return StationMenuOut(station=StationOut.model_validate(station), categories=result)


# ---------- Nhân viên: báo còn / hết ----------
@router.put(
    "/{station_id}/items/{item_id}/availability", response_model=AvailabilityOut
)
def set_availability(
    station_id: int,
    item_id: int,
    payload: AvailabilityIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("STAFF", "ADMIN")),
):
    """Nhân viên chỉ được sửa món ở cửa hàng của mình; admin sửa được mọi cửa hàng."""
    if user["role"] == "STAFF" and user["station_id"] != station_id:
        raise HTTPException(
            status_code=403, detail="Bạn chỉ được cập nhật món ở cửa hàng của mình"
        )
    _get_station(db, station_id)
    item = db.get(MenuItem, item_id)
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Không tìm thấy món")

    row = db.scalar(
        select(StationItemAvailability).where(
            StationItemAvailability.station_id == station_id,
            StationItemAvailability.item_id == item_id,
        )
    )
    if row is None:
        row = StationItemAvailability(station_id=station_id, item_id=item_id)
        db.add(row)
    row.is_available = payload.available
    row.updated_by = user["id"]
    db.commit()

    AVAILABILITY_CHANGES.labels(available=str(payload.available).lower()).inc()
    return AvailabilityOut(
        station_id=station_id, item_id=item_id, available=payload.available
    )


# ---------- Admin: quản lý cửa hàng ----------
@router.post("", response_model=StationOut, status_code=201)
def create_station(
    payload: StationIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    station = Station(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/{station_id}", response_model=StationOut)
def update_station(
    station_id: int,
    payload: StationIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    station = _get_station(db, station_id)
    for field, value in payload.model_dump().items():
        setattr(station, field, value)
    db.commit()
    db.refresh(station)
    return station


@router.delete("/{station_id}", status_code=204)
def deactivate_station(
    station_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    """Xóa mềm: đơn cũ bên order-service vẫn tham chiếu station_id này."""
    station = _get_station(db, station_id)
    station.is_active = False
    db.commit()
