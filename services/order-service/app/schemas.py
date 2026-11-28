from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------- Request ----------
class OrderItemIn(BaseModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    """Đặt trước trên web: chưa trả tiền, khách trả ở trạm 1 (tiền mặt hoặc ZaloPay)."""
    station_id: int = Field(gt=0)
    license_plate: str = Field(min_length=4, max_length=15)
    contact_phone: str = Field(pattern=r"^0\d{9}$", description="Số điện thoại 10 số")
    # Khách sẽ tới trạm 1 trong bao nhiêu phút; đơn được giữ thêm 10 phút du di
    arrival_minutes: Literal[15, 30, 45] = 30
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


class CheckIn(BaseModel):
    """Trạm 1 nhận đơn: khách chọn trả tiền mặt hay ZaloPay ngay tại trạm.

    Gọi lại khi đơn đang chờ thanh toán để đổi cách trả (ví dụ ZaloPay lỗi, trả tiền mặt).
    """
    payment_method: Literal["ZALOPAY", "CASH"]


class PlateUpdate(BaseModel):
    license_plate: str = Field(min_length=4, max_length=15)

    @field_validator("license_plate")
    @classmethod
    def normalize_plate(cls, v: str) -> str:
        return v.strip().upper()


# ---------- Response ----------
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_id: int
    item_name: str
    unit_price: int
    quantity: int
    prep_minutes: int = 3


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
    payment_method: str | None = None   # chọn ở trạm 1
    pickup_code: str | None = None      # mã 4 số khách đọc ở trạm 1 và trạm 2
    contact_phone: str | None = None
    subtotal: int
    discount_amount: int
    total_amount: int
    coupon_code: str | None
    expected_arrival_at: datetime | None = None  # giờ khách hẹn tới trạm 1
    hold_expires_at: datetime | None = None      # quá giờ này nhân viên được hủy đơn treo
    is_overdue: bool = False
    checked_in_at: datetime | None = None        # trạm 1 nhận đơn
    confirmed_at: datetime | None = None         # đã trả tiền, vào bếp
    arrived_at: datetime | None = None           # cách làm cũ, đơn mới không dùng
    prep_minutes: int = 0               # số phút bếp cần để làm cả đơn
    estimated_ready_at: datetime | None = None  # giờ dự kiến món xong
    created_at: datetime
    items: list[OrderItemOut]
    history: list[StatusHistoryOut]
    
class StatusUpdate(BaseModel):
    # Bếp: PREPARING, READY. Trạm 2: COMPLETED.
    # AWAITING_PAYMENT do trạm 1 (check-in), CONFIRMED do payment-service báo đã trả tiền.
    status: Literal["PREPARING", "READY", "COMPLETED"]
    note: str | None = Field(default=None, max_length=200)


class StationOrderStats(BaseModel):
    station_id: int
    total_orders: int
    active_orders: int        # đang trong hàng đợi
    completed_orders: int
    cancelled_orders: int
    revenue: int              # tổng tiền các đơn đã hoàn thành (VND)
    today_orders: int
    today_revenue: int


class StationWaitTime(BaseModel):
    station_id: int
    queue_count: int          # số đơn đang chờ làm / chờ giao
    estimated_minutes: int    # thời gian chờ ước tính cho đơn mới


class InternalOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    station_id: int
    status: str
    payment_method: str | None = None
    total_amount: int


class PaymentConfirmIn(BaseModel):
    transaction_ref: str | None = Field(default=None, max_length=100)
    # Cách khách đã trả thật sự (payment-service biết rõ); None ở phiên bản cũ
    method: Literal["ZALOPAY", "CASH"] | None = None


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


class CouponAvailableOut(BaseModel):
    code: str
    discount_type: str
    discount_value: int
    valid_to: date
    discount_amount: int  # số tiền giảm cho giỏ hàng hiện tại


class CouponCheckOut(BaseModel):
    code: str
    discount_amount: int
    total_amount: int