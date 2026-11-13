from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app import config, models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.routers import catalog, internal, stations
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if config.SEED_DATA:
        with SessionLocal() as db:
            seed_if_empty(db)
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
