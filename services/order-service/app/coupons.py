from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Coupon


def apply_coupon(db: Session, code: str | None, subtotal: int) -> tuple[int, str | None]:
    """Trả về (số tiền giảm, mã đã áp dụng). Mã sai/hết hạn thì báo lỗi 400."""
    if not code:
        return 0, None

    coupon = db.scalar(select(Coupon).where(Coupon.code == code))
    today = date.today()
    if (
        coupon is None
        or not coupon.is_active
        or not (coupon.valid_from <= today <= coupon.valid_to)
    ):
        raise HTTPException(
            status_code=400, detail="Mã giảm giá không hợp lệ hoặc đã hết hạn"
        )

    if coupon.discount_type == "PERCENT":
        discount = subtotal * coupon.discount_value // 100
    else:  # FIXED
        discount = coupon.discount_value

    return min(discount, subtotal), coupon.code