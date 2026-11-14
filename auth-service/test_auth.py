import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from security import INTERNAL_KEY

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_register_and_login_flow():
    # 1. Đăng ký khách hàng
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": "testuser@drivethru.vn",
            "password": "Password123",
            "full_name": "Nguyễn Văn Test",
            "phone": "0901234567",
        },
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "testuser@drivethru.vn"
    assert user_data["role"] == "customer"

    # 2. Đăng nhập
    login_res = client.post(
        "/api/auth/login",
        json={"email": "testuser@drivethru.vn", "password": "Password123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    # 3. Gọi /api/auth/me
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["full_name"] == "Nguyễn Văn Test"

    # 4. Làm mới token bằng refresh_token
    ref_res = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_res.status_code == 200
    assert "access_token" in ref_res.json()


def test_telegram_link_and_bind():
    # Đăng ký & đăng nhập
    client.post(
        "/api/auth/register",
        json={
            "email": "tele@drivethru.vn",
            "password": "Password123",
            "full_name": "Tele User",
        },
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": "tele@drivethru.vn", "password": "Password123"},
    )
    token = login_res.json()["access_token"]

    # Tạo link token
    link_res = client.post(
        "/api/auth/telegram/link-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert link_res.status_code == 200
    link_token = link_res.json()["link_token"]

    # Gọi internal bind từ Telegram bot
    bind_res = client.post(
        "/internal/auth/telegram/bind",
        json={"token": link_token, "chat_id": "987654321"},
        headers={"X-Internal-Key": INTERNAL_KEY},
    )
    assert bind_res.status_code == 200
    assert bind_res.json()["telegram_chat_id"] == "987654321"

