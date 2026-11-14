import os
import logging
from datetime import datetime, timedelta
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter

from database import engine, Base, SessionLocal, get_db
from models import User, RefreshToken
from schemas import (
    RegisterRequest,
    LoginRequest,
    CreateStaffRequest,
    RefreshRequest,
    TelegramBindRequest,
    UserResponse,
    TokenResponse,
    TelegramLinkResponse,
)
from security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_random_token,
    get_current_user,
    verify_internal_key,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auth-service")

BOT_USERNAME = os.getenv("BOT_USERNAME", "DriveThruSOABot")

# Custom Prometheus Business Metrics
AUTH_LOGINS_TOTAL = Counter(
    "auth_logins_total",
    "Total login attempts by role and status",
    ["role", "status"],
)
AUTH_REGISTRATIONS_TOTAL = Counter(
    "auth_registrations_total",
    "Total new customer registrations",
)


def seed_default_accounts():
    """Tự động tạo sẵn các tài khoản mẫu (Admin, Nhân viên, Khách hàng) để demo và xem ngay trong TablePlus."""
    db = SessionLocal()
    try:
        samples = [
            {
                "email": "admin@drivethru.vn",
                "password": "Password123",
                "full_name": "Quản Trị Viên Hệ Thống",
                "phone": "0901111111",
                "role": "admin",
                "station_id": None,
            },
            {
                "email": "staff1@drivethru.vn",
                "password": "Password123",
                "full_name": "Trần Văn Bếp (CN Quận 1)",
                "phone": "0902222222",
                "role": "staff",
                "station_id": 1,
            },
            {
                "email": "staff2@drivethru.vn",
                "password": "Password123",
                "full_name": "Lê Thị Thu Ngân (CN Quận 7)",
                "phone": "0903333333",
                "role": "staff",
                "station_id": 2,
            },
            {
                "email": "khachhang@drivethru.vn",
                "password": "Password123",
                "full_name": "Nguyễn Hữu Tân (Khách Hàng)",
                "phone": "0909999999",
                "role": "customer",
                "station_id": None,
            },
        ]
        for acc in samples:
            exists = db.query(User).filter(User.email == acc["email"]).first()
            if not exists:
                user = User(
                    email=acc["email"],
                    hashed_password=hash_password(acc["password"]),
                    full_name=acc["full_name"],
                    phone=acc["phone"],
                    role=acc["role"],
                    station_id=acc["station_id"],
                )
                db.add(user)
        db.commit()
        logger.info(">>> Đã kiểm tra và tạo sẵn các tài khoản mẫu trong auth_db!")
    except Exception as e:
        logger.warning(f"Không thể seed dữ liệu mẫu: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        seed_default_accounts()
        logger.info(">>> Kết nối auth_db và tạo bảng thành công!")
    except Exception as e:
        logger.error(f"Lỗi kết nối auth_db: {e}")
    yield


app = FastAPI(
    title="Drive-Thru Auth Service",
    description="Dịch vụ Đăng ký, Đăng nhập, Phân quyền JWT và Liên kết Telegram Bot",
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


# ===== 1. ĐĂNG KÝ KHÁCH HÀNG =====
@app.post(
    "/api/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Đăng ký tài khoản Khách hàng",
)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được sử dụng. Vui lòng chọn email khác.",
        )

    new_user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        phone=req.phone,
        role="customer",
        station_id=None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    AUTH_REGISTRATIONS_TOTAL.inc()
    return new_user


# ===== 2. ĐĂNG NHẬP & CẤP JWT + REFRESH TOKEN =====
@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Đăng nhập và nhận JWT Access Token + Refresh Token",
)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        AUTH_LOGINS_TOTAL.labels(role="unknown", status="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        )

    if not user.is_active:
        AUTH_LOGINS_TOTAL.labels(role=user.role, status="locked").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị khóa.",
        )

    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "station_id": user.station_id,
    }
    access_token = create_access_token(data=token_payload)

    # Lưu Refresh Token vào bảng refresh_tokens
    raw_refresh = generate_random_token(32)
    refresh_record = RefreshToken(
        user_id=user.id,
        token=raw_refresh,
        expires_at=datetime.utcnow() + timedelta(days=7),
        revoked=False,
    )
    db.add(refresh_record)
    db.commit()

    AUTH_LOGINS_TOTAL.labels(role=user.role, status="success").inc()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        user=user,
    )


# ===== 3. LÀM MỚI ACCESS TOKEN BẰNG REFRESH TOKEN =====
@app.post(
    "/api/auth/refresh",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Cấp lại Access Token mới từ Refresh Token",
)
def refresh_access_token(req: RefreshRequest, db: Session = Depends(get_db)):
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == req.refresh_token, RefreshToken.revoked == False)
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã hết hạn.",
        )

    user = db.query(User).filter(User.id == record.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "station_id": user.station_id,
    }
    new_access_token = create_access_token(data=token_payload)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=record.token,
        token_type="bearer",
        user=user,
    )


# ===== 4. LẤY THÔNG TIN TÀI KHOẢN HIỆN TẠI =====
@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Xem thông tin người dùng đang đăng nhập",
)
def get_me(
    current_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = int(current_payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    return user


# ===== 5. QUẢN LÝ NHÂN VIÊN (DÀNH CHO ADMIN) =====
@app.post(
    "/api/auth/staff",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Staff Management (Admin)"],
    summary="[Admin] Tạo tài khoản nhân viên gán theo cửa hàng (station)",
)
def create_staff(
    req: CreateStaffRequest,
    current_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (Admin) mới có quyền tạo tài khoản nhân viên.",
        )

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email nhân viên này đã tồn tại.",
        )

    new_staff = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        phone=req.phone,
        role="staff",
        station_id=req.station_id,
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)
    return new_staff


@app.get(
    "/api/auth/staff",
    response_model=List[UserResponse],
    tags=["Staff Management (Admin)"],
    summary="[Admin] Lấy danh sách toàn bộ nhân viên",
)
def list_staff(
    current_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin mới được xem danh sách nhân viên.",
        )
    return db.query(User).filter(User.role == "staff").order_by(User.id.asc()).all()


@app.patch(
    "/api/auth/staff/{staff_id}/toggle-active",
    response_model=UserResponse,
    tags=["Staff Management (Admin)"],
    summary="[Admin] Khóa hoặc mở khóa tài khoản nhân viên",
)
def toggle_staff_status(
    staff_id: int,
    current_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thực hiện.")
    staff = db.query(User).filter(User.id == staff_id, User.role == "staff").first()
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên.")
    staff.is_active = not staff.is_active
    db.commit()
    db.refresh(staff)
    return staff


# ===== 6. LIÊN KẾT TÀI KHOẢN VỚI TELEGRAM BOT =====
@app.post(
    "/api/auth/telegram/link-token",
    response_model=TelegramLinkResponse,
    tags=["Telegram Integration"],
    summary="Tạo token một lần và đường link kết nối Telegram cho khách hàng",
)
def generate_telegram_link(
    current_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = int(current_payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    # Tạo token ngắn gọn để truyền qua /start <token> (Telegram giới hạn 64 ký tự)
    link_token = f"USR{user.id}_{generate_random_token(12)}"
    user.telegram_link_token = link_token
    db.commit()

    telegram_url = f"https://t.me/{BOT_USERNAME}?start={link_token}"
    return TelegramLinkResponse(
        link_token=link_token,
        bot_username=BOT_USERNAME,
        telegram_url=telegram_url,
    )


# ===== 7. INTERNAL APIs (CHỈ CÁC MICROSERVICE GỌI NỘI BỘ) =====
@app.post(
    "/internal/auth/telegram/bind",
    tags=["Internal Service-to-Service"],
    summary="[Internal] Bot Telegram gọi để gắn chat_id vào tài khoản web khi khách bấm /start <token>",
)
def bind_telegram_chat_id(
    req: TelegramBindRequest,
    db: Session = Depends(get_db),
    _ok: bool = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_link_token == req.token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mã liên kết Telegram không hợp lệ hoặc đã được sử dụng.",
        )

    user.telegram_chat_id = str(req.chat_id)
    user.telegram_link_token = None  # Xóa token một lần sau khi đã gắn thành công
    db.commit()
    db.refresh(user)

    return {
        "status": "linked",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "telegram_chat_id": user.telegram_chat_id,
    }


@app.get(
    "/internal/auth/users/{user_id}",
    response_model=UserResponse,
    tags=["Internal Service-to-Service"],
    summary="[Internal] Lấy thông tin user và telegram_chat_id từ order-service / feedback-service",
)
def get_user_internal(
    user_id: int,
    db: Session = Depends(get_db),
    _ok: bool = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User không tồn tại.")
    return user


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": "auth-service"}
