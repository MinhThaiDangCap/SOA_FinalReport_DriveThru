"""Mã nhận món: 4 chữ số ngẫu nhiên, không trùng trong ngày tại cùng chi nhánh.

Khách đọc mã ở trạm 1 (xác nhận, thanh toán) và trạm 2 (nhận món); nhân viên luôn đối chiếu
thêm biển số. Không dùng số thứ tự đơn để không bị đoán và không lộ số lượng đơn.
"""

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order

VN_TZ = timezone(timedelta(hours=7))
_rng = random.SystemRandom()


def vn_today() -> date:
    return datetime.now(VN_TZ).date()


def new_pickup_code(db: Session, station_id: int, day: date) -> str | None:
    """Bốc một mã chưa dùng trong ngày. Hết mã (9.000 đơn/ngày) thì trả None.

    Hai đơn bốc trúng cùng mã cùng lúc thì ràng buộc UNIQUE trong database chặn đơn sau,
    nơi gọi bốc lại (xem create_order).
    """
    used = set(
        db.scalars(
            select(Order.pickup_code).where(
                Order.station_id == station_id, Order.pickup_date == day
            )
        )
    )
    free = [c for c in (f"{n}" for n in range(1000, 10000)) if c not in used]
    return _rng.choice(free) if free else None


def normalize_plate(value: str) -> str:
    """'51A-123.45' -> '51A12345', để tìm theo biển số không phụ thuộc dấu."""
    return "".join(ch for ch in value.upper() if ch.isalnum())
