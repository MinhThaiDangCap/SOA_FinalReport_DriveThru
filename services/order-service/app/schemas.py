from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    
class StatusUpdate(BaseModel):
    # Nhân viên chỉ được đặt 3 trạng thái này.
    # CONFIRMED do payment-service báo, ARRIVED và CANCELLED do khách.
    status: Literal["PREPARING", "READY", "COMPLETED"]
    note: str | None = Field(default=None, max_length=200)


class InternalOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    station_id: int
    status: str
    payment_method: str
    total_amount: int


class PaymentConfirmIn(BaseModel):
    transaction_ref: str | None = Field(default=None, max_length=100)
    
    # ---------- Mã giảm giá ----------
class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    discount_type: Literal["PERCENT", "FIXED"]
    discount_value: int = Field(gt=0)
    valid_from: date
    valid_to: date
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def check_rules(self):
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to phải sau hoặc bằng valid_from")
        if self.discount_type == "PERCENT" and self.discount_value > 100:
            raise ValueError("Giảm theo % không được vượt quá 100")
        return self


class CouponUpdate(BaseModel):
    # Không cho đổi code (đơn cũ đã lưu code này)
    discount_type: Literal["PERCENT", "FIXED"] | None = None
    discount_value: int | None = Field(default=None, gt=0)
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool | None = None


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    discount_type: str
    discount_value: int
    valid_from: date
    valid_to: date
    is_active: bool


class CouponCheckOut(BaseModel):
    code: str
    discount_amount: int
    total_amount: int