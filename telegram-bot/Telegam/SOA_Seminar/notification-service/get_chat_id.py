import os

import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit("Chưa có TELEGRAM_BOT_TOKEN trong file .env")

data = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
if not data.get("ok"):
    raise SystemExit(f"Lỗi: {data}")
if not data["result"]:
    raise SystemExit("Chưa có tin nhắn nào. Hãy nhắn cho bot trước rồi chạy lại.")

seen = set()
for upd in data["result"]:
    msg = upd.get("message") or upd.get("channel_post") or {}
    chat = msg.get("chat", {})
    if chat.get("id") and chat["id"] not in seen:
        seen.add(chat["id"])
        name = chat.get("username") or chat.get("title") or chat.get("first_name")
        print(f"chat_id = {chat['id']}  ({chat.get('type')}, {name})")
