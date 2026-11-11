from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- Request ----------
class OrderItemIn(BaseModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    station_id: int = Field(gt=0)
    license_plate: str = Field(min_length=4, max_length=15)
    payment_method: Literal["VNPAY", "CASH"]
    coupon_code: str | None = Field(default=None, max_length=30)
    items: list[OrderItemIn] = Field(min_length=1)

    @field_validator("license_plate")
    @classmethod
    def normalize_plate(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("coupon_code")
    @classmethod
    def normalize_coupon(cls, v: str | None) -> str | None:
        v = v.strip().upper() if v else None
        return v or None


# ---------- Response ----------
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int
    item_name: str
    unit_price: int
    quantity: int


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    changed_by: int | None
    note: str | None
    changed_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    station_id: int
    license_plate: str
    status: str
    payment_method: str
    subtotal: int
    discount_amount: int
    total_amount: int
    coupon_code: str | None
    created_at: datetime
    items: list[OrderItemOut]
    history: list[StatusHistoryOut]