from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, MenuItem
from app.schemas import CategoryIn, CategoryOut, MenuItemIn, MenuItemOut
from app.security import require_roles

router = APIRouter(prefix="/api/menu")


# ==================== Danh mục ====================
def _get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy danh mục")
    return category


def _check_category_name(db: Session, name: str, exclude_id: int | None = None):
    query = select(Category).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="Tên danh mục đã tồn tại")


@router.get("/categories", response_model=list[CategoryOut], tags=["categories"])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(Category).order_by(Category.sort_order, Category.id)
    ).all()


@router.post(
    "/categories", response_model=CategoryOut, status_code=201, tags=["categories"]
)
def create_category(
    payload: CategoryIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    _check_category_name(db, payload.name)
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put(
    "/categories/{category_id}", response_model=CategoryOut, tags=["categories"]
)
def update_category(
    category_id: int,
    payload: CategoryIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    category = _get_category(db, category_id)
    _check_category_name(db, payload.name, exclude_id=category_id)
    category.name = payload.name
    category.sort_order = payload.sort_order
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204, tags=["categories"])
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    category = _get_category(db, category_id)
    has_items = db.scalar(
        select(MenuItem.id).where(MenuItem.category_id == category_id).limit(1)
    )
    if has_items is not None:
        raise HTTPException(
            status_code=409,
            detail="Danh mục còn món, hãy chuyển hoặc xóa món trước",
        )
    db.delete(category)
    db.commit()


# ==================== Món ====================
def _get_item(db: Session, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy món")
    return item


@router.get("/items", response_model=list[MenuItemOut], tags=["items"])
def list_items(
    category_id: int | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """Danh sách món (chưa gắn với cửa hàng). Khách nên dùng /stations/{id}/menu."""
    query = select(MenuItem).order_by(MenuItem.id)
    if category_id is not None:
        query = query.where(MenuItem.category_id == category_id)
    if not include_inactive:
        query = query.where(MenuItem.is_active.is_(True))
    return db.scalars(query).all()


@router.get("/items/{item_id}", response_model=MenuItemOut, tags=["items"])
def get_item(item_id: int, db: Session = Depends(get_db)):
    return _get_item(db, item_id)


@router.post("/items", response_model=MenuItemOut, status_code=201, tags=["items"])
def create_item(
    payload: MenuItemIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=400, detail="Danh mục không tồn tại")
    item = MenuItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/items/{item_id}", response_model=MenuItemOut, tags=["items"])
def update_item(
    item_id: int,
    payload: MenuItemIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    item = _get_item(db, item_id)
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=400, detail="Danh mục không tồn tại")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204, tags=["items"])
def deactivate_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("ADMIN")),
):
    """Xóa mềm: đơn cũ bên order-service vẫn tham chiếu menu_item_id này."""
    item = _get_item(db, item_id)
    item.is_active = False
    db.commit()
