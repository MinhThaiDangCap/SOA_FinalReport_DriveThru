import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderStatus(str, enum.Enum):
    # Luồng 2 trạm:
    # HOLD (đặt trên web, có mã, chưa trả tiền, bếp chưa thấy)
    # -> AWAITING_PAYMENT (trạm 1 đã nhận đơn, khách đang trả tiền mặt / ZaloPay)
    # -> CONFIRMED (đã trả tiền, vào hàng đợi bếp) -> PREPARING -> READY (mời ra trạm 2)
    # -> COMPLETED (trạm 2 đã giao). Đơn chưa trả tiền có thể CANCELLED.
    HOLD = "HOLD"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    # Hai trạng thái của cách làm cũ (trả ZaloPay ngay khi đặt, khách báo "đã đến"),
    # giữ lại để đọc được đơn cũ trong database
    PENDING_PAYMENT = "PENDING_PAYMENT"
    ARRIVED = "ARRIVED"


class Order(Base):
    __tablename__ = "orders"
    # Mã nhận món không trùng trong ngày tại cùng chi nhánh
    __table_args__ = (
        UniqueConstraint("station_id", "pickup_date", "pickup_code", name="uq_orders_pickup"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(index=True)  # users.id bên auth_db
    station_id: Mapped[int] = mapped_column(index=True)   # stations.id bên menu_db
    license_plate: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=OrderStatus.HOLD.value, index=True
    )
    # ZALOPAY | CASH, khách chọn khi đã tới trạm 1 (đơn đang treo thì chưa có)
    payment_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Mã 4 số khách đọc ở trạm 1 và trạm 2
    pickup_code: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # ngày theo giờ VN
    contact_phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    # Khách hẹn tới trạm 1 lúc nào; quá hold_expires_at thì nhân viên được hủy đơn
    expected_arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(  # trạm 1 nhận đơn
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(   # đã trả tiền, vào bếp
        DateTime(timezone=True), nullable=True
    )
    subtotal: Mapped[int] = mapped_column(default=0)          # VND, số nguyên
    discount_amount: Mapped[int] = mapped_column(default=0)
    total_amount: Mapped[int] = mapped_column(default=0)
    coupon_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Số phút bếp cần để làm cả đơn (xem app/estimate.py)
    prep_minutes: Mapped[int] = mapped_column(default=0, server_default="0")
    # Giờ dự kiến món xong, tính lại khi đơn vào hàng đợi và khi bếp bắt đầu làm
    estimated_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Cách làm cũ: lúc khách bấm "Tôi đã đến" (đơn mới không dùng)
    arrived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )

    @property
    def is_overdue(self) -> bool:
        """Đơn đang treo đã quá hạn giữ: trạm 1 tô đỏ, nhân viên được hủy (không tự hủy)."""
        if self.status != OrderStatus.HOLD.value or self.hold_expires_at is None:
            return False
        exp = self.hold_expires_at
        if exp.tzinfo is None:  # SQLite trả datetime không có múi giờ
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    menu_item_id: Mapped[int]            # menu_items.id bên menu_db
    item_name: Mapped[str] = mapped_column(String(100))  # snapshot tên
    unit_price: Mapped[int]                               # snapshot giá
    quantity: Mapped[int]
    prep_minutes: Mapped[int] = mapped_column(default=3, server_default="3")  # snapshot

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[int | None] = mapped_column(nullable=True)  # users.id hoặc NULL nếu hệ thống
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="history")


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    discount_type: Mapped[str] = mapped_column(String(10))  # PERCENT | FIXED
    discount_value: Mapped[int]
    valid_from: Mapped[date]
    valid_to: Mapped[date]
    is_active: Mapped[bool] = mapped_column(default=True)