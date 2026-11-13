from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app import models  # noqa: F401
from app.database import Base, engine
from app.routers import payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Payment Service", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.include_router(payments.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "payment-service"}