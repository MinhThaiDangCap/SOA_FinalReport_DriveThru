from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base


class User(Base):
    """Bảng lưu thông tin tài khoản Khách hàng, Nhân viên và Admin"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)

    # Vai trò: "customer" | "staff" | "admin"
    role = Column(String(20), default="customer", nullable=False)

    # ID cửa hàng dành cho nhân viên (staff)
    station_id = Column(Integer, nullable=True)

    # Liên kết Telegram (dành cho thông báo & khảo sát qua Bot)
    telegram_chat_id = Column(String(50), nullable=True, index=True)
    telegram_link_token = Column(String(100), nullable=True, unique=True, index=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RefreshToken(Base):
    """Bảng lưu refresh token theo thiết kế ERD của auth_db"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

