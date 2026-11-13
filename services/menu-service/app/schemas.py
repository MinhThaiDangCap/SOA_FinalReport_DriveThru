from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(v: str) -> str:
    return v.strip()


def _strip_or_none(v: str | None) -> str | None:
    v = v.strip() if v else None
    return v or None


# ---------- Station ----------
class StationIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=255)
    opening_hours: str | None = Field(default=None, max_length=50)
    is_active: bool = True

    _name = field_validator("name", "address")(_strip)
    _hours = field_validator("opening_hours")(_strip_or_none)


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    opening_hours: str | None
    is_active: bool


# ---------- Category ----------
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0

    _name = field_validator("name")(_strip)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


# ---------- Menu item ----------
class MenuItemIn(BaseModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    price: int = Field(ge=0, le=10_000_000)  # VND
    image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    _name = field_validator("name")(_strip)
    _optional = field_validator("description", "image_url")(_strip_or_none)


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    description: str | None
    price: int
    image_url: str | None
    is_active: bool
    created_at: datetime


# ---------- Menu theo cửa hàng (khách xem) ----------
class StationMenuItem(BaseModel):
    id: int
    name: str
    description: str | None
    price: int
    image_url: str | None
    available: bool


class StationMenuCategory(BaseModel):
    id: int
    name: str
    items: list[StationMenuItem]


class StationMenuOut(BaseModel):
    station: StationOut
    categories: list[StationMenuCategory]


# ---------- Còn / hết ----------
class AvailabilityIn(BaseModel):
    available: bool


class AvailabilityOut(BaseModel):
    station_id: int
    item_id: int
    available: bool


# ---------- Nội bộ (order-service gọi) ----------
class InternalItemOut(BaseModel):
    id: int
    name: str
    price: int
    available: bool
