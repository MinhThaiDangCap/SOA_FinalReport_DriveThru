from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.coupons import apply_coupon
from app.database import get_db
from app.models import Coupon
from app.schemas import CouponCheckOut, CouponCreate, CouponOut, CouponUpdate
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/api/orders/coupons", tags=["coupons"])


def get_coupon_or_404(db: Session, coupon_id: int) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã giảm giá")
    return coupon


# ---------- Khách: kiểm tra mã trước khi đặt ----------
# Khai báo TRƯỚC các route /{coupon_id} để "check" không bị hiểu là một ID
@router.get("/check", response_model=CouponCheckOut)
def check_coupon(
    code: str = Query(min_length=1, max_length=30),
    subtotal: int = Query(gt=0, description="Tổng tiền hàng trước giảm giá (VND)"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    discount, applied = apply_coupon(db, code.strip().upper(), subtotal)
    return CouponCheckOut(
        code=applied, discount_amount=discount, total_amount=subtotal - discount
    )


# ---------- Admin: tạo mã ----------
@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("ADMIN")),
):
    if db.scalar(select(Coupon).where(Coupon.code == payload.code)):
        raise HTTPException(status_code=409, detail="Mã giảm giá đã tồn tại")

    coupon = Coupon(**payload.model_dump())
    db.add(coupon)
    try:
        db.commit()
    except IntegrityError:  # hai admin tạo cùng lúc
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã giảm giá đã tồn tại")
    db.refresh(coupon)
    return coupon


# ---------- Admin: danh sách, lọc theo ngày ----------
@router.get("", response_model=list[CouponOut])
def list_coupons(
    valid_on: date | None = Query(
        default=None, description="Chỉ lấy mã có hiệu lực vào ngày này (YYYY-MM-DD)"
    ),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("ADMIN")),
):
    stmt = select(Coupon).order_by(Coupon.id.desc())
    if valid_on is not None:
        stmt = stmt.where(Coupon.valid_from <= valid_on, Coupon.valid_to >= valid_on)
    if is_active is not None:
        stmt = stmt.where(Coupon.is_active == is_active)
    return db.scalars(stmt).all()


# ---------- Admin: sửa / bật tắt ----------
@router.patch("/{coupon_id}", response_model=CouponOut)
def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("ADMIN")),
):
    coupon = get_coupon_or_404(db, coupon_id)

    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    for field, value in changes.items():
        setattr(coupon, field, value)

    # Kiểm tra lại các quy tắc sau khi gộp thay đổi
    if coupon.valid_to < coupon.valid_from:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ngày kết thúc phải sau ngày bắt đầu")
    if coupon.discount_type == "PERCENT" and coupon.discount_value > 100:
        db.rollback()
        raise HTTPException(status_code=400, detail="Giảm theo % không được vượt quá 100")

    db.commit()
    db.refresh(coupon)
    return coupon


# ---------- Admin: xóa ----------
@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("ADMIN")),
):
    coupon = get_coupon_or_404(db, coupon_id)
    db.delete(coupon)  # an toàn: đơn cũ chỉ lưu chuỗi code, không có khóa ngoại
    db.commit()