import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
MENU_DB = os.getenv("MENU_DB", "menu_db")

# Đặt DATABASE_URL để ghi đè (vd. sqlite:///./menu.db khi dev không có Postgres,
# hoặc sqlite:// khi chạy test). Bình thường để trống và dùng Postgres.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{MENU_DB}"
)

JWT_SECRET = os.getenv("JWT_SECRET", "change_me_to_a_long_random_string")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

INTERNAL_KEY = os.getenv("INTERNAL_KEY", "change_me_internal_key")

# true = khi database còn trống thì tự thêm cửa hàng, danh mục, món mẫu
SEED_DATA = os.getenv("SEED_DATA", "true").lower() == "true"
