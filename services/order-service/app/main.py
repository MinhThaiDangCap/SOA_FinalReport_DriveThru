from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app import models  # noqa: F401
from app.database import Base, engine
from app.routers import coupon_admin, internal, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # create_all không thêm cột vào bảng đã có: thêm tay cột mới cho database cũ
    with engine.begin() as conn:
        for sql in (
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS arrived_at TIMESTAMPTZ",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS prep_minutes INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS estimated_ready_at TIMESTAMPTZ",
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS prep_minutes INTEGER NOT NULL DEFAULT 3",
        ):
            conn.execute(text(sql))
    yield


app = FastAPI(title="Order Service", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.include_router(coupon_admin.router)  # phải đứng trước orders.router
app.include_router(orders.router)
app.include_router(internal.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "order-service"}