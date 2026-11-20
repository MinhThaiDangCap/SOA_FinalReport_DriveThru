import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from models import User
from security import hash_password

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
    assert user_data["role"] == "CUSTOMER"

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


def test_admin_create_and_toggle_staff():
    db = TestingSessionLocal()
    admin = User(
        email="admin@drivethru.vn",
        hashed_password=hash_password("Password123"),
        full_name="Admin Test",
        role="ADMIN",
    )
    db.add(admin)
    db.commit()
    db.close()

    login_res = client.post(
        "/api/auth/login",
        json={"email": "admin@drivethru.vn", "password": "Password123"},
    )
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    staff_res = client.post(
        "/api/auth/staff",
        json={
            "email": "staff_new@drivethru.vn",
            "password": "Password123",
            "full_name": "Nhân Viên Mới",
            "phone": "0905555555",
            "station_id": 1,
        },
        headers=headers,
    )
    assert staff_res.status_code == 201
    staff_id = staff_res.json()["id"]

    toggle_res = client.patch(f"/api/auth/staff/{staff_id}/toggle-active", headers=headers)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False
