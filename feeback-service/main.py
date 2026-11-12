import os
import logging
from typing import List, Optional
from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Header, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter

from database import engine, Base, SessionLocal, get_db
from models import Review
from schemas import ReviewCreate, TelegramReviewCreate, ReviewResponse, StationStatsResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("feedback-service")

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_drivethru_2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "change_me_internal_key")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "my-secret-key")

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")
# Cho phép chạy độc lập khi order-service của bạn A chưa bật (đặt false khi tích hợp thật)
ORDER_SERVICE_FALLBACK = os.getenv("ORDER_SERVICE_FALLBACK", "true").lower() == "true"

# Custom Prometheus Metrics (Phục vụ Grafana Dashboard)
REVIEWS_CREATED_TOTAL = Counter(
    "reviews_created_total",
    "Total number of customer reviews created",
    ["station_id", "rating", "source"],
)
NEGATIVE_REVIEWS_TOTAL = Counter(
    "negative_reviews_total",
    "Total number of negative reviews (1-2 stars)",
    ["station_id"],
)


def seed_sample_reviews():
    """Tạo sẵn dữ liệu đánh giá mẫu cho Trạm 1 và Trạm 2 để xem trên TablePlus và Admin Dashboard."""
    db = SessionLocal()
    try:
        if db.query(Review).count() == 0:
            samples = [
                Review(
                    order_id=1001,
                    customer_id=4,
                    station_id=1,
                    rating=5,
                    comment="Nhận đồ ăn tại làn xe cực nhanh, nhân viên nhìn biển số giao đúng ngay lập tức!",
                    source="web",
                ),
                Review(
                    order_id=1002,
                    customer_id=4,
                    station_id=1,
                    rating=4,
                    comment="Burger bò phô mai nóng hổi, khoai tây giòn.",
                    source="telegram",
                ),
                Review(
                    order_id=1003,
                    customer_id=5,
                    station_id=1,
                    rating=2,
                    comment="Nước ngọt bị tan đá hơi nhạt, chờ ở làn xe mất gần 7 phút.",
                    source="web",
                ),
                Review(
                    order_id=1004,
                    customer_id=6,
                    station_id=1,
                    rating=1,
                    comment="Giao thiếu 1 gói tương ớt và khăn giấy dù đã ghi chú.",
                    source="telegram",
                ),
                Review(
                    order_id=1005,
                    customer_id=4,
                    station_id=2,
                    rating=5,
                    comment="Chi nhánh Quận 7 rộng rãi, bấm Tôi đã đến là 30 giây sau có nhân viên mang ra.",
                    source="web",
                ),
                Review(
                    order_id=1006,
                    customer_id=7,
                    station_id=2,
                    rating=2,
                    comment="Món gà rán hơi nguội vào khung giờ tối.",
                    source="web",
                ),
            ]
            db.add_all(samples)
            db.commit()
            logger.info(">>> Đã tạo 6 đánh giá mẫu trong feedback_db!")
    except Exception as e:
        logger.warning(f"Lỗi khi seed dữ liệu mẫu: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        seed_sample_reviews()
        logger.info(">>> Đã kết nối feedback_db và kiểm tra bảng 'reviews' thành công!")
    except Exception as e:
        logger.error(f"Lỗi kết nối feedback_db: {e}")
    yield


app = FastAPI(
    title="Drive-Thru Feedback Service",
    description="Dịch vụ Đánh giá đơn hàng và Thống kê chất lượng cửa hàng (Web & Telegram Bot)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Giải mã JWT Token để lấy user_id và role."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để thực hiện thao tác này.",
        )
    try:
        token = authorization.replace("Bearer ", "").strip()
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn.")
    except Exception:
        raise HTTPException(status_code=401, detail="Token không hợp lệ.")


def verify_internal_key(x_internal_key: Optional[str] = Header(None)):
    if x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="X-Internal-Key không hợp lệ.")
    return True


def fetch_order_from_order_service(order_id: int, fallback_customer_id: int, fallback_station_id: int) -> dict:
    """
    Gọi nội bộ sang order-service kèm X-Internal-Key, có timeout (3s) và retry (2 lần).
    Kiểm tra đơn hàng có tồn tại và đã COMPLETED chưa.
    """
    url = f"{ORDER_SERVICE_URL}/internal/orders/{order_id}"
    headers = {"X-Internal-Key": INTERNAL_KEY}
    transport = httpx.HTTPTransport(retries=2)

    try:
        with httpx.Client(transport=transport, timeout=3.0) as client:
            res = client.get(url, headers=headers)
            if res.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Đơn hàng #{order_id} không tồn tại.")
            if res.status_code == 200:
                return res.json()
            raise HTTPException(
                status_code=502,
                detail=f"Order Service trả về lỗi {res.status_code}.",
            )
    except httpx.RequestError:
        if ORDER_SERVICE_FALLBACK:
            logger.warning(f"order-service chưa bật, dùng fallback cho đơn #{order_id}")
            return {
                "id": order_id,
                "status": "COMPLETED",
                "customer_id": fallback_customer_id,
                "station_id": fallback_station_id,
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kết nối tới Order Service. Vui lòng thử lại sau.",
        )


def send_negative_review_alert(review: Review):
    """Gửi cảnh báo ngầm sang notification-service (Telegram) khi khách đánh giá 1-2 sao."""
    if review.rating > 2:
        return
    try:
        url = f"{NOTIFICATION_SERVICE_URL}/notify"
        headers = {"X-API-Key": SERVICE_API_KEY}
        payload = {
            "service": "feedback-service",
            "level": "WARNING",
            "title": f"Cảnh báo đánh giá thấp ({review.rating} sao) tại Trạm #{review.station_id}",
            "message": (
                f"Đơn hàng: #{review.order_id}\n"
                f"Khách hàng ID: {review.customer_id}\n"
                f"Số sao: {review.rating}/5 ⭐\n"
                f"Lý do: {review.comment or 'Không có'}"
            ),
        }
        with httpx.Client(timeout=5.0) as client:
            client.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.warning(f"Không gửi được cảnh báo Telegram (không làm ảnh hưởng đánh giá): {e}")


# ===== 1. KHÁCH HÀNG GỬI ĐÁNH GIÁ TRÊN WEB =====
@app.post(
    "/api/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Customer Reviews"],
    summary="[Khách hàng] Đánh giá đơn hàng đã hoàn thành (1-5 sao)",
)
def create_review(
    req: ReviewCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_payload: dict = Depends(get_current_user),
):
    customer_id = int(user_payload.get("sub"))

    # 1. Kiểm tra mỗi đơn chỉ được đánh giá 1 lần
    existing = db.query(Review).filter(Review.order_id == req.order_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn hàng #{req.order_id} đã được đánh giá trước đó.",
        )

    # 2. Gọi order-service kiểm tra trạng thái COMPLETED và đúng chủ đơn
    order_info = fetch_order_from_order_service(
        order_id=req.order_id,
        fallback_customer_id=customer_id,
        fallback_station_id=req.station_id or 1,
    )

    if order_info.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ được đánh giá đơn hàng đã COMPLETED (Trạng thái hiện tại: {order_info.get('status')}).",
        )

    if int(order_info.get("customer_id", customer_id)) != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không thể đánh giá đơn hàng của người khác.",
        )

    station_id = int(order_info.get("station_id") or req.station_id or 1)

    # 3. Lưu vào feedback_db
    new_review = Review(
        order_id=req.order_id,
        customer_id=customer_id,
        station_id=station_id,
        rating=req.rating,
        comment=req.comment,
        source="web",
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    # 4. Cập nhật Prometheus Metrics & bắn cảnh báo Telegram nếu 1-2 sao
    REVIEWS_CREATED_TOTAL.labels(
        station_id=str(station_id),
        rating=str(req.rating),
        source="web",
    ).inc()
    if req.rating <= 2:
        NEGATIVE_REVIEWS_TOTAL.labels(station_id=str(station_id)).inc()
        background_tasks.add_task(send_negative_review_alert, new_review)

    return new_review


# ===== 2. INTERNAL API: NHẬN ĐÁNH GIÁ TỪ TELEGRAM BOT =====
@app.post(
    "/internal/reviews/telegram",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Internal (Telegram Bot)"],
    summary="[Internal] Lưu kết quả khảo sát từ Telegram Bot vào feedback_db",
)
def create_review_from_telegram(
    req: TelegramReviewCreate,
    db: Session = Depends(get_db),
    _ok: bool = Depends(verify_internal_key),
):
    existing = db.query(Review).filter(Review.order_id == req.order_id).first()
    if existing:
        existing.rating = req.rating
        existing.comment = req.comment
        existing.source = "telegram"
        db.commit()
        db.refresh(existing)
        return existing

    new_review = Review(
        order_id=req.order_id,
        customer_id=req.customer_id or 1,
        station_id=req.station_id or 1,
        rating=req.rating,
        comment=req.comment,
        source="telegram",
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    REVIEWS_CREATED_TOTAL.labels(
        station_id=str(new_review.station_id),
        rating=str(req.rating),
        source="telegram",
    ).inc()
    if req.rating <= 2:
        NEGATIVE_REVIEWS_TOTAL.labels(station_id=str(new_review.station_id)).inc()

    return new_review


# ===== 3. ADMIN XEM THỐNG KÊ SAO & GÓP Ý TIÊU CỰC THEO CỬA HÀNG =====
@app.get(
    "/api/reviews/stations/{station_id}/stats",
    response_model=StationStatsResponse,
    tags=["Admin Analytics"],
    summary="[Admin] Xem điểm trung bình, phân bổ sao và góp ý tiêu cực theo cửa hàng",
)
def get_station_stats(station_id: int, db: Session = Depends(get_db)):
    reviews = (
        db.query(Review)
        .filter(Review.station_id == station_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    total = len(reviews)

    if total == 0:
        return StationStatsResponse(
            station_id=station_id,
            total_reviews=0,
            average_rating=0.0,
            rating_breakdown={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            negative_reviews=[],
        )

    avg_rating = round(sum(r.rating for r in reviews) / total, 2)
    breakdown = {i: 0 for i in range(1, 6)}
    negatives = []

    for r in reviews:
        breakdown[r.rating] = breakdown.get(r.rating, 0) + 1
        if r.rating in [1, 2]:
            negatives.append(r)

    return StationStatsResponse(
        station_id=station_id,
        total_reviews=total,
        average_rating=avg_rating,
        rating_breakdown=breakdown,
        negative_reviews=negatives,
    )


# ===== 4. DANH SÁCH ĐÁNH GIÁ CỦA CỬA HÀNG =====
@app.get(
    "/api/reviews/stations/{station_id}",
    response_model=List[ReviewResponse],
    tags=["Admin Analytics"],
    summary="Lấy danh sách đánh giá của cửa hàng (có lọc theo số sao)",
)
def list_station_reviews(
    station_id: int,
    rating: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
):
    q = db.query(Review).filter(Review.station_id == station_id)
    if rating:
        q = q.filter(Review.rating == rating)
    return q.order_by(Review.created_at.desc()).all()


# ===== 5. KIỂM TRA ĐƠN HÀNG ĐÃ ĐÁNH GIÁ CHƯA =====
@app.get(
    "/api/reviews/orders/{order_id}",
    response_model=Optional[ReviewResponse],
    tags=["Customer Reviews"],
    summary="Kiểm tra xem một đơn hàng đã có đánh giá chưa",
)
def get_order_review(order_id: int, db: Session = Depends(get_db)):
    return db.query(Review).filter(Review.order_id == order_id).first()


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": "feedback-service"}

