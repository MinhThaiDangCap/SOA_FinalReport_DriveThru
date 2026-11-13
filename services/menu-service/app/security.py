import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Giải mã JWT, trả về {"id", "role", "station_id"}."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Thiếu token đăng nhập")
    try:
        payload = jwt.decode(
            credentials.credentials,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
        )
        return {
            "id": int(payload["sub"]),
            "role": payload.get("role"),
            "station_id": payload.get("station_id"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token không hợp lệ")


def require_roles(*roles: str):
    """Ví dụ: Depends(require_roles("STAFF", "ADMIN"))"""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Không đủ quyền")
        return user

    return checker


def verify_internal_key(x_internal_key: str | None = Header(default=None)):
    """Dùng cho các endpoint /internal/* (service gọi service)."""
    if x_internal_key != config.INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Sai internal key")
