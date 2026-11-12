import logging
import os
from typing import Literal, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from notifier import TelegramError, TelegramNotifier

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("notification-service")

API_KEY = os.getenv("SERVICE_API_KEY", "my-secret-key")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "change_me_internal_key")
notifier = TelegramNotifier()

app = FastAPI(
    title="Drive-Thru Notification Service",
    version="1.0.0",
    description="Nhận yêu cầu thông báo trạng thái đơn hàng & gửi khảo sát tới khách hàng qua Telegram.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)


class Notification(BaseModel):
    service: str = Field(..., examples=["order-service"])
    level: Literal["INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    title: str = Field(..., examples=["Đơn hàng #1001 đã sẵn sàng!"])
    message: str = Field(..., examples=["Món ăn của bạn đã chuẩn bị xong tại Làn Drive-Thru."])
    chat_id: Optional[str] = Field(None, description="Telegram chat_id của khách hàng (bỏ trống sẽ gửi về Admin)")


class SurveyRequest(BaseModel):
    order_id: str = Field(..., examples=["1001"])
    service_name: str = Field("Drive-Thru", examples=["Drive-Thru CN Quận 1"])
    chat_id: Optional[str] = Field(None, description="Telegram chat_id của khách hàng nhận phiếu đánh giá")


def _send_survey(r: SurveyRequest):
    try:
        notifier.send_survey(r.order_id, r.service_name, chat_id=r.chat_id)
    except (TelegramError, ValueError) as e:
        log.error("Gửi khảo sát thất bại: %s", e)


def _send(n: Notification):
    try:
        notifier.notify(n.level, n.title, n.message, service=n.service, chat_id=n.chat_id)
    except (TelegramError, ValueError) as e:
        log.error("Gửi Telegram thất bại: %s", e)


def _verify_key(x_api_key: Optional[str], x_internal_key: Optional[str]):
    if x_api_key == API_KEY or x_internal_key == INTERNAL_KEY:
        return True
    raise HTTPException(status_code=401, detail="Invalid API key or Internal key")


@app.post("/notify", status_code=202)
def notify(
    n: Notification,
    background: BackgroundTasks,
    x_api_key: Optional[str] = Header(None),
    x_internal_key: Optional[str] = Header(None),
):
    _verify_key(x_api_key, x_internal_key)
    background.add_task(_send, n)
    return {"status": "queued", "service": n.service, "level": n.level, "chat_id": n.chat_id}


@app.post("/survey", status_code=202)
def survey(
    r: SurveyRequest,
    background: BackgroundTasks,
    x_api_key: Optional[str] = Header(None),
    x_internal_key: Optional[str] = Header(None),
):
    _verify_key(x_api_key, x_internal_key)
    background.add_task(_send_survey, r)
    return {"status": "queued", "order_id": r.order_id, "chat_id": r.chat_id}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification-service"}
