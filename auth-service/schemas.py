from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72, description="Mật khẩu tối thiểu 6 ký tự")
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^0\d{9}$", description="Số điện thoại 10 số bắt đầu bằng 0")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72, description="Mật khẩu tối thiểu 6 ký tự")


class CreateStaffRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^0\d{9}$")
    station_id: int = Field(..., ge=1, description="ID cửa hàng nhân viên phụ trách")
    role: Literal["STAFF", "KITCHEN"] = Field(
        "STAFF", description="STAFF: nhân viên trạm 1/trạm 2, KITCHEN: bếp"
    )


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    station_id: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
