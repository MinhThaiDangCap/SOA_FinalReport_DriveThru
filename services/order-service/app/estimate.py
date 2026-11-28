"""Hàng đợi bếp và ước lượng giờ món xong.

Cách tính (cố ý giữ đơn giản, không tự học từ dữ liệu cũ):
- Mỗi món có số phút làm cố định (prep_minutes, admin đặt bên menu-service).
- Thời gian làm 1 đơn = món lâu nhất + 1 phút cho mỗi 2 phần thêm
  (các món trong đơn được làm song song, càng nhiều phần càng lâu hơn chút).
- Bếp mỗi chi nhánh làm được kitchen_capacity đơn cùng lúc.

Thứ tự bếp làm (chỉ các đơn ĐÃ TRẢ TIỀN ở trạm 1, tức khách đang chờ ở bãi):
1. Đơn đang làm (PREPARING) giữ nguyên chỗ.
2. Đơn đã chờ quá AGING_MINUTES kể từ lúc vào bếp: lên trước, ai vào trước làm trước,
   để đơn lâu không bị đơn nhanh chen mãi.
3. Còn lại: đơn làm NHANH trước (ít phút hơn), bằng nhau thì ai vào trước làm trước.
   Đơn nhanh xong sớm thì xe rời bãi sớm, thời gian chờ trung bình của khách giảm.

Giờ xong dự kiến: xếp lần lượt các đơn theo thứ tự trên vào kitchen_capacity "chỗ" của bếp,
đơn nào cũng lấy chỗ trống sớm nhất. Tính lại mỗi khi hàng đợi thay đổi.
"""

import heapq
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus

DEFAULT_PREP_MINUTES = 3      # món không rõ số phút
DEFAULT_KITCHEN_CAPACITY = 2  # chi nhánh không rõ số đơn làm cùng lúc
TYPICAL_ORDER_MINUTES = 5     # đơn "điển hình", dùng cho thời gian chờ ở trang chủ
AGING_MINUTES = 10            # chờ quá lâu thì được đẩy lên đầu hàng bếp

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


def _prep(order: Order) -> int:
    # Đơn tạo trước khi có tính năng này chưa có prep_minutes: coi như đơn điển hình
    return order.prep_minutes or TYPICAL_ORDER_MINUTES


def _entered_kitchen(order: Order) -> datetime:
    return _aware(order.confirmed_at or order.created_at or now_utc())


def waited_minutes(order: Order, now: datetime) -> float:
    return (now - _entered_kitchen(order)).total_seconds() / 60


def remaining_minutes(order: Order, now: datetime) -> float:
    """Số phút bếp còn phải làm cho đơn đang làm dở."""
    if order.estimated_ready_at is None:
        return _prep(order)
    return max((_aware(order.estimated_ready_at) - now).total_seconds() / 60, 0)


def kitchen_order(orders: list[Order], now: datetime) -> list[Order]:
    """Sắp các đơn trong bếp theo thứ tự ưu tiên (xem đầu file)."""
    preparing = sorted(
        (o for o in orders if o.status == OrderStatus.PREPARING.value),
        key=lambda o: (remaining_minutes(o, now), o.id),
    )

    def key(o: Order):
        if waited_minutes(o, now) >= AGING_MINUTES:
            return (0, _entered_kitchen(o), o.id)          # chờ lâu: ai vào trước làm trước
        return (1, _prep(o), _entered_kitchen(o), o.id)    # còn lại: đơn nhanh trước

    waiting = sorted((o for o in orders if o.status == OrderStatus.CONFIRMED.value), key=key)
    return preparing + waiting


def schedule(orders: list[Order], capacity: int, now: datetime) -> tuple[dict[int, float], list[float]]:
    """Xếp các đơn CONFIRMED vào bếp theo thứ tự ưu tiên.

    Trả về ({order_id: số phút nữa thì xong}, [phút nữa thì từng chỗ của bếp rảnh]).
    """
    ordered = kitchen_order(orders, now)
    slots = [remaining_minutes(o, now) for o in ordered if o.status == OrderStatus.PREPARING.value]
    slots += [0.0] * max(capacity - len(slots), 0)
    heapq.heapify(slots)

    finish: dict[int, float] = {}
    for o in ordered:
        if o.status != OrderStatus.CONFIRMED.value:
            continue
        start = heapq.heappop(slots)       # chỗ trống sớm nhất của bếp
        finish[o.id] = start + _prep(o)
        heapq.heappush(slots, finish[o.id])
    return finish, sorted(slots)


def lock_station(db: Session, station_id: int) -> None:
    """Khóa hàng đợi bếp của một chi nhánh đến hết transaction (PostgreSQL).

    Nhiều đơn vào bếp cùng lúc (giờ trưa) sẽ lần lượt được xếp, không đơn nào bị tính
    giờ dự kiến mà "không thấy" đơn kia. SQLite (test) chạy tuần tự nên không cần.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 70000 + station_id})


def kitchen_orders(db: Session, station_id: int) -> list[Order]:
    return list(
        db.scalars(
            select(Order).where(
                Order.station_id == station_id, Order.status.in_(KITCHEN_STATUSES)
            )
        )
    )


def recompute_station(db: Session, station_id: int, capacity: int) -> list[Order]:
    """Tính lại giờ xong dự kiến của mọi đơn đang chờ bếp ở chi nhánh. Không commit.

    Đơn đang làm giữ giờ đã đặt lúc bếp bắt đầu làm. Trả về hàng đợi theo thứ tự ưu tiên.
    """
    now = now_utc()
    orders = kitchen_orders(db, station_id)
    finish, _ = schedule(orders, capacity, now)
    for o in orders:
        if o.id in finish:
            o.estimated_ready_at = now + timedelta(minutes=math.ceil(finish[o.id]))
    return kitchen_order(orders, now)


def start_preparing(order: Order) -> None:
    """Bếp bắt đầu làm: xong sau đúng số phút của đơn."""
    order.estimated_ready_at = now_utc() + timedelta(minutes=_prep(order))


def wait_minutes_for_new_order(db: Session, station_id: int, capacity: int) -> int:
    """Một đơn mới vào bếp lúc này phải chờ bao lâu mới bắt đầu được làm (trang chủ)."""
    _, slots = schedule(kitchen_orders(db, station_id), capacity, now_utc())
    return math.ceil(slots[0]) if slots else 0
