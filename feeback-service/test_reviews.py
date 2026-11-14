import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, get_current_user
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
        "role": "customer",
    }


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
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

