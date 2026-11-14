from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Mật khẩu tối thiểu 6 ký tự")
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateStaffRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    station_id: int = Field(..., description="ID cửa hàng nhân viên phụ trách")


class RefreshRequest(BaseModel):
    refresh_token: str


class TelegramBindRequest(BaseModel):
    token: str = Field(..., description="Token một lần từ lệnh /start <token>")
    chat_id: str = Field(..., description="Telegram chat_id của khách hàng")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    station_id: Optional[int]
    telegram_chat_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TelegramLinkResponse(BaseModel):
    link_token: str
    bot_username: str
    telegram_url: str

