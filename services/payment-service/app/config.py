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

VNP_TMN_CODE = os.getenv("VNP_TMN_CODE", "")
VNP_HASH_SECRET = os.getenv("VNP_HASH_SECRET", "")
VNP_URL = os.getenv("VNP_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNP_RETURN_URL = os.getenv("VNP_RETURN_URL", "http://localhost:5173/payment/result")

# true = thanh toán giả, không gọi VNPay thật
MOCK_MODE = os.getenv("PAYMENT_MOCK_MODE", "false").lower() == "true"
# true = trang return cũng xử lý kết quả (dùng khi VNPay chưa gọi được IPN vào máy local)
PROCESS_ON_RETURN = os.getenv("VNP_PROCESS_ON_RETURN", "false").lower() == "true"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8004")