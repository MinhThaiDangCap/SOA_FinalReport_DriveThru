import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
PAYMENT_DB = os.getenv("PAYMENT_DB", "payment_db")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{PAYMENT_DB}"
)

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
INTERNAL_KEY = os.environ["INTERNAL_KEY"]

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://127.0.0.1:8003")

# true = thanh toán giả, không gọi ZaloPay thật
MOCK_MODE = os.getenv("PAYMENT_MOCK_MODE", "false").lower() == "true"
# Địa chỉ công khai của payment-service (ZaloPay gọi callback vào đây; chạy local thì cần ngrok)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8004")

# ZaloPay. Mặc định là bộ key sandbox công khai của ZaloPay (app_id 2554, không có tiền thật)
ZALOPAY_APP_ID = int(os.getenv("ZALOPAY_APP_ID") or "2554")
ZALOPAY_KEY1 = os.getenv("ZALOPAY_KEY1") or "sdngKKJmqEMzvh5QQcdD2A9XBSKUNaYn"  # ký yêu cầu gửi đi
ZALOPAY_KEY2 = os.getenv("ZALOPAY_KEY2") or "trMrHtvjo6myautxDUiAcYsVtaeQ8nhf"  # kiểm tra dữ liệu ZaloPay gửi về
ZALOPAY_ENDPOINT = (os.getenv("ZALOPAY_ENDPOINT") or "https://sb-openapi.zalopay.vn").rstrip("/")
# Trang kết quả của web, ZaloPay chuyển khách về đây sau khi thanh toán
ZALOPAY_REDIRECT_URL = (
    os.getenv("ZALOPAY_REDIRECT_URL") or "http://localhost:5173/payment/result"
)
# ZaloPay gọi callback vào đây khi khách trả xong (chạy local thì cần ngrok)
ZALOPAY_CALLBACK_URL = (
    os.getenv("ZALOPAY_CALLBACK_URL") or f"{PUBLIC_BASE_URL}/api/payments/zalopay/callback"
)
