import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
ORDER_DB = os.getenv("ORDER_DB", "order_db")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{ORDER_DB}"
)

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
INTERNAL_KEY = os.environ["INTERNAL_KEY"]

MENU_SERVICE_URL = os.getenv("MENU_SERVICE_URL", "http://localhost:8002")

# true = không gọi menu-service thật, dùng món giả (để test khi B chưa xong)
MENU_MOCK = os.getenv("MENU_MOCK", "false").lower() == "true"