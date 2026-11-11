from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Station(Base):
    """Cửa hàng drive-thru."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(255))
    opening_hours: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)  # False = ngừng hoạt động
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Category(Base):
    """Danh mục món (Burger, Đồ uống...)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base):
    """Món ăn. Giá dùng chung cho mọi cửa hàng, tính bằng VND (số nguyên)."""

    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[int] = mapped_column()
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)  # False = ngừng bán hẳn
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="items")


class StationItemAvailability(Base):
    """Tình trạng còn/hết của một món tại một cửa hàng.

    Không có dòng nào cho cặp (station, item) nghĩa là món đang CÒN.
    Nhân viên chỉ tạo/sửa dòng khi báo hết hoặc báo có lại.
    """

    __tablename__ = "station_item_availability"
    __table_args__ = (UniqueConstraint("station_id", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    is_available: Mapped[bool] = mapped_column(default=True)
    updated_by: Mapped[int | None] = mapped_column(nullable=True)  # users.id bên auth_db
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
