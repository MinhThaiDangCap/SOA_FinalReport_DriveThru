import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from main import app, get_current_user

# Giữ hàm thật để test trường hợp order-service không phản hồi
REAL_FETCH_ORDER = main.fetch_order_from_order_service
from database import Base, get_db

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


def override_get_current_user():
    return {
        "sub": "1",
        "email": "customer@drivethru.vn",
        "role": "CUSTOMER",
    }


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    # Giả lập kết quả trả về từ order-service để unit test chạy độc lập cả trong lẫn ngoài Docker
    monkeypatch.setattr(
        main,
        "fetch_order_from_order_service",
        lambda order_id, fallback_customer_id, fallback_station_id: {
            "id": order_id,
            "status": "COMPLETED",
            "customer_id": fallback_customer_id,
            "station_id": fallback_station_id,
        },
    )
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_low_rating_requires_comment():
    # Đánh giá 1 sao nhưng không có comment -> Bắt buộc báo lỗi 422
    res = client.post(
        "/api/reviews",
        json={"order_id": 2001, "station_id": 1, "rating": 1, "comment": ""},
    )
    assert res.status_code == 422


def test_create_review_and_stats():
    # 1. Tạo đánh giá 5 sao
    res1 = client.post(
        "/api/reviews",
        json={
            "order_id": 2002,
            "station_id": 1,
            "rating": 5,
            "comment": "Rất tuyệt vời!",
        },
    )
    assert res1.status_code == 201

    # 2. Tạo đánh giá 2 sao có lý do
    res2 = client.post(
        "/api/reviews",
        json={
            "order_id": 2003,
            "station_id": 1,
            "rating": 2,
            "comment": "Chờ hơi lâu.",
        },
    )
    assert res2.status_code == 201

    # 3. Kiểm tra thống kê cửa hàng 1
    stats_res = client.get("/api/reviews/stations/1/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_reviews"] == 2
    assert stats["average_rating"] == 3.5
    assert len(stats["negative_reviews"]) == 1


def test_get_order_review_requires_login_and_owner():
    client.post("/api/reviews", json={"order_id": 2004, "station_id": 1, "rating": 5})

    # Chủ đơn xem được
    res = client.get("/api/reviews/orders/2004")
    assert res.status_code == 200 and res.json()["rating"] == 5
    # Đơn chưa đánh giá -> null
    assert client.get("/api/reviews/orders/9999").json() is None

    # Khách khác -> 403
    app.dependency_overrides[get_current_user] = lambda: {"sub": "2", "role": "CUSTOMER"}
    try:
        assert client.get("/api/reviews/orders/2004").status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = override_get_current_user

    # Không đăng nhập -> 401
    del app.dependency_overrides[get_current_user]
    try:
        assert client.get("/api/reviews/orders/2004").status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = override_get_current_user


# ---------- Ràng buộc nghiệp vụ và xử lý lỗi ----------
def fake_order(status="COMPLETED", customer_id=1, station_id=1):
    return lambda order_id, fallback_customer_id, fallback_station_id: {
        "id": order_id, "status": status, "customer_id": customer_id, "station_id": station_id,
    }


def test_each_order_can_be_reviewed_once():
    body = {"order_id": 3001, "station_id": 1, "rating": 4}
    assert client.post("/api/reviews", json=body).status_code == 201
    assert client.post("/api/reviews", json=body).status_code == 400


def test_rating_must_be_between_1_and_5():
    for rating in (0, 6):
        res = client.post("/api/reviews", json={"order_id": 3002, "rating": rating, "comment": "x"})
        assert res.status_code == 422


def test_cannot_review_order_not_completed(monkeypatch):
    monkeypatch.setattr(main, "fetch_order_from_order_service", fake_order(status="PREPARING"))
    res = client.post("/api/reviews", json={"order_id": 3003, "rating": 5})
    assert res.status_code == 400


def test_cannot_review_someone_elses_order(monkeypatch):
    monkeypatch.setattr(main, "fetch_order_from_order_service", fake_order(customer_id=99))
    res = client.post("/api/reviews", json={"order_id": 3004, "rating": 5})
    assert res.status_code == 403


def test_station_is_taken_from_order_service_not_client(monkeypatch):
    """Khách gửi station_id sai thì vẫn lưu theo cửa hàng thật của đơn."""
    monkeypatch.setattr(main, "fetch_order_from_order_service", fake_order(station_id=3))
    res = client.post("/api/reviews", json={"order_id": 3005, "station_id": 1, "rating": 5})
    assert res.status_code == 201 and res.json()["station_id"] == 3


def test_create_review_requires_login():
    del app.dependency_overrides[get_current_user]
    try:
        res = client.post("/api/reviews", json={"order_id": 3006, "rating": 5})
        assert res.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = override_get_current_user


def test_list_station_reviews_filter_by_rating():
    for oid, rating in ((3010, 5), (3011, 5), (3012, 3)):
        client.post("/api/reviews", json={"order_id": oid, "station_id": 1, "rating": rating})
    assert len(client.get("/api/reviews/stations/1").json()) == 3
    assert len(client.get("/api/reviews/stations/1?rating=5").json()) == 2
    assert client.get("/api/reviews/stations/1?rating=9").status_code == 422


def test_order_service_down_returns_503(monkeypatch):
    """order-service không phản hồi (và tắt fallback như trong Docker) -> 503, không lưu đánh giá."""
    monkeypatch.setattr(main, "fetch_order_from_order_service", REAL_FETCH_ORDER)
    monkeypatch.setattr(main, "ORDER_SERVICE_FALLBACK", False)
    monkeypatch.setattr(main, "ORDER_SERVICE_URL", "http://127.0.0.1:9")  # cổng không có gì chạy
    res = client.post("/api/reviews", json={"order_id": 3020, "rating": 5})
    assert res.status_code == 503
    assert client.get("/api/reviews/stations/1").json() == []
