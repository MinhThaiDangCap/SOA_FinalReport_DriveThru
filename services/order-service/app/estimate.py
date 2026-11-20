"""Ước lượng thời gian làm xong đơn.

Cách tính (cố ý giữ đơn giản, không tự học từ dữ liệu cũ):
- Mỗi món có số phút làm cố định (prep_minutes, admin đặt bên menu-service).
- Thời gian làm 1 đơn = món lâu nhất + 1 phút cho mỗi 2 phần thêm
  (các món trong đơn được làm song song, càng nhiều phần càng lâu hơn chút).
- Bếp mỗi cửa hàng làm được kitchen_capacity đơn cùng lúc.
- Thời gian chờ = tổng phút còn lại của các đơn xếp trước / kitchen_capacity.
- Giờ xong dự kiến = bây giờ + thời gian chờ + thời gian làm đơn này.
"""

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus

DEFAULT_PREP_MINUTES = 3      # món không rõ số phút
DEFAULT_KITCHEN_CAPACITY = 2  # cửa hàng không rõ số đơn làm cùng lúc
TYPICAL_ORDER_MINUTES = 5     # đơn "điển hình", dùng cho thời gian chờ ở trang chủ

# Các đơn bếp còn phải làm (READY trở đi thì bếp đã xong)
KITCHEN_STATUSES = [OrderStatus.CONFIRMED.value, OrderStatus.PREPARING.value]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite trả datetime không có múi giờ: coi là UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def order_prep_minutes(items: list[tuple[int, int]]) -> int:
    """items: [(prep_minutes của món, số lượng)]. Trả về số phút làm cả đơn."""
    if not items:
        return 0
    longest = max(prep for prep, _ in items)
    total_qty = sum(qty for _, qty in items)
    return longest + (total_qty - 1) // 2


def remaining_minutes(order: Order, now: datetime) -> float:
    """Số phút bếp còn phải làm cho đơn này."""
    # Đơn tạo trước khi có tính năng này chưa có prep_minutes: coi như đơn điển hình
    prep = order.prep_minutes or TYPICAL_ORDER_MINUTES
    if order.status == OrderStatus.CONFIRMED.value:
        return prep
    if order.status == OrderStatus.PREPARING.value:
        if order.estimated_ready_at is None:
            return prep
        left = (_aware(order.estimated_ready_at) - now).total_seconds() / 60
        return max(left, 0)
    return 0


def backlog_minutes(
    db: Session, station_id: int, before_order_id: int | None = None
) -> float:
    """Tổng phút bếp còn phải làm ở cửa hàng.

    before_order_id: chỉ tính các đơn xếp trước đơn này (bếp làm đơn cũ trước).
    """
    stmt = select(Order).where(
        Order.station_id == station_id, Order.status.in_(KITCHEN_STATUSES)
    )
    if before_order_id is not None:
        stmt = stmt.where(Order.id < before_order_id)
    now = now_utc()
    return sum(remaining_minutes(o, now) for o in db.scalars(stmt))


def wait_minutes(backlog: float, capacity: int) -> int:
    return math.ceil(backlog / max(capacity, 1))


def set_estimate(db: Session, order: Order, capacity: int) -> None:
    """Tính lại giờ xong dự kiến khi đơn vào hàng đợi hoặc khi bếp bắt đầu làm."""
    now = now_utc()
    if order.status == OrderStatus.CONFIRMED.value:
        db.flush()  # đơn mới cần có id để biết đơn nào xếp trước
        wait = wait_minutes(backlog_minutes(db, order.station_id, order.id), capacity)
        order.estimated_ready_at = now + timedelta(minutes=wait + order.prep_minutes)
    elif order.status == OrderStatus.PREPARING.value:
        order.estimated_ready_at = now + timedelta(minutes=order.prep_minutes)
    elif order.status == OrderStatus.PENDING_PAYMENT.value:
        order.estimated_ready_at = None  # chưa trả tiền thì bếp chưa làm
