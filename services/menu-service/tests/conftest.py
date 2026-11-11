import os
import sys
from pathlib import Path

# Phải đặt trước khi import app: dùng SQLite trong RAM, không seed dữ liệu mẫu
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DATA"] = "false"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"
os.environ["INTERNAL_KEY"] = "test-internal-key"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def make_token(role: str, user_id: int = 1, station_id: int | None = None) -> dict:
    """Header Authorization với JWT giống auth-service phát."""
    token = jwt.encode(
        {"sub": str(user_id), "role": role, "station_id": station_id},
        config.JWT_SECRET,
        algorithm=config.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


ADMIN = make_token("ADMIN")
CUSTOMER = make_token("CUSTOMER", user_id=9)
INTERNAL = {"X-Internal-Key": "test-internal-key"}


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def data(client):
    """1 cửa hàng, 1 danh mục, 2 món."""
    station = client.post(
        "/api/menu/stations",
        json={"name": "Quận 7", "address": "19 Nguyễn Hữu Thọ"},
        headers=ADMIN,
    ).json()
    category = client.post(
        "/api/menu/categories", json={"name": "Burger", "sort_order": 1}, headers=ADMIN
    ).json()
    items = [
        client.post(
            "/api/menu/items",
            json={"category_id": category["id"], "name": name, "price": price},
            headers=ADMIN,
        ).json()
        for name, price in [("Burger bò", 45000), ("Burger gà", 42000)]
    ]
    return {"station": station, "category": category, "items": items}
