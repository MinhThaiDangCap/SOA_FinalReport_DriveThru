import csv
import os
from pathlib import Path

# Mặc định: SOA_Seminar/data/customers.csv (cùng file Java ghi). Có thể đổi bằng biến CUSTOMERS_FILE trong .env
FILE = Path(os.getenv("CUSTOMERS_FILE") or Path(__file__).resolve().parent.parent / "data" / "customers.csv")


def load():
    """Trả về dict {MÃ_KHÁCH: {code, chat_id, name, username, registered_at}}"""
    if not FILE.exists():
        return {}
    with open(FILE, encoding="utf-8", newline="") as f:
        return {row["code"].strip().upper(): row for row in csv.DictReader(f) if row.get("code")}