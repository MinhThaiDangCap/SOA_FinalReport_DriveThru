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


# ---------- Lỗi đầu vào, xác thực và phân quyền ----------
def register(email="khach@drivethru.vn", password="Password123", **extra):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Khách Test", **extra},
    )


def login(email, password="Password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def create_admin_headers():
    db = TestingSessionLocal()
    db.add(User(email="admin2@drivethru.vn", hashed_password=hash_password("Password123"),
                full_name="Admin", role="ADMIN"))
    db.commit()
    db.close()
    token = login("admin2@drivethru.vn").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_rejects_duplicate_email():
    assert register().status_code == 201
    dup = register()
    assert dup.status_code == 400


def test_register_validates_input():
    assert register(password="123").status_code == 422           # mật khẩu < 6 ký tự
    assert register(email="khong-phai-email").status_code == 422
    assert register(phone="12345").status_code == 422             # SĐT phải 10 số, bắt đầu bằng 0
    assert register(phone="0901234567").status_code == 201


def test_login_wrong_password_returns_401():
    register()
    assert login("khach@drivethru.vn", "SaiMatKhau1").status_code == 401
    assert login("khong-ton-tai@drivethru.vn").status_code == 401


def test_password_is_hashed_not_stored_plain():
    register()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "khach@drivethru.vn").first()
    db.close()
    assert user.hashed_password != "Password123"
    assert user.hashed_password.startswith("$2")                  # bcrypt


def test_me_requires_valid_token():
    assert client.get("/api/auth/me").status_code in (401, 403)
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer token-gia"})
    assert bad.status_code == 401


def test_invalid_refresh_token_returns_401():
    assert client.post("/api/auth/refresh", json={"refresh_token": "khong-hop-le"}).status_code == 401


def test_customer_cannot_manage_staff():
    register()
    token = login("khach@drivethru.vn").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"email": "nv@drivethru.vn", "password": "Password123",
            "full_name": "Nhân Viên", "station_id": 1}
    assert client.post("/api/auth/staff", json=body, headers=headers).status_code == 403
    assert client.get("/api/auth/staff", headers=headers).status_code == 403


def test_locked_staff_cannot_login():
    headers = create_admin_headers()
    staff = client.post(
        "/api/auth/staff",
        json={"email": "nv2@drivethru.vn", "password": "Password123",
              "full_name": "Nhân Viên 2", "station_id": 2},
        headers=headers,
    ).json()
    assert login("nv2@drivethru.vn").status_code == 200
    assert staff["station_id"] == 2

    client.patch(f"/api/auth/staff/{staff['id']}/toggle-active", headers=headers)  # khóa
    assert login("nv2@drivethru.vn").status_code == 403


def test_internal_user_api_requires_internal_key():
    user_id = register().json()["id"]
    assert client.get(f"/internal/auth/users/{user_id}").status_code == 401
    wrong = client.get(f"/internal/auth/users/{user_id}", headers={"X-Internal-Key": "sai"})
    assert wrong.status_code == 401

    from security import INTERNAL_KEY
    ok = client.get(f"/internal/auth/users/{user_id}", headers={"X-Internal-Key": INTERNAL_KEY})
    assert ok.status_code == 200 and ok.json()["email"] == "khach@drivethru.vn"
