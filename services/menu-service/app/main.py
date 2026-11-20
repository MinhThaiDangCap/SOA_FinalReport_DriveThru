from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import inspect, text

from app import config, models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.routers import catalog, internal, stations
from app.seed import fill_prep_minutes, rename_old_brand, seed_if_empty


def add_missing_columns() -> bool:
    """create_all không thêm cột vào bảng đã có: thêm tay cột mới cho database cũ.

    Trả về True nếu vừa thêm cột prep_minutes (để điền số phút mẫu một lần).
    """
    if engine.dialect.name != "postgresql":
        return False  # test dùng SQLite, bảng luôn được tạo mới
    columns = {c["name"] for c in inspect(engine).get_columns("menu_items")}
    added_prep = "prep_minutes" not in columns
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS prep_minutes INTEGER NOT NULL DEFAULT 3"
        ))
        conn.execute(text(
            "ALTER TABLE stations ADD COLUMN IF NOT EXISTS kitchen_capacity INTEGER NOT NULL DEFAULT 2"
        ))
    return added_prep


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    added_prep = add_missing_columns()
    if config.SEED_DATA:
        with SessionLocal() as db:
            seed_if_empty(db)
            rename_old_brand(db)
            if added_prep:
                fill_prep_minutes(db)
    yield


app = FastAPI(
    title="Menu Service",
    version="1.0.0",
    description="Cửa hàng, danh mục, món và tình trạng còn/hết theo cửa hàng.",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(stations.router)
app.include_router(catalog.router)
app.include_router(internal.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "menu-service"}
