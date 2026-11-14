import html
import logging
import os
import socket
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("notifier")

API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4096

LEVEL_ICON = {
    "INFO": "ℹ️",
    "SUCCESS": "✅",
    "WARNING": "⚠️",
    "ERROR": "❌",
    "CRITICAL": "🚨",
}


class TelegramError(Exception):
    pass


class TelegramNotifier:
    def __init__(self, token=None, chat_id=None, timeout=10, max_retries=3):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = timeout
        self.max_retries = max_retries
        self.host = socket.gethostname()

    def _call(self, method, payload=None, file_field=None, file_path=None):
        if not self.token:
            raise TelegramError("Thiếu TELEGRAM_BOT_TOKEN (xem file .env)")
        url = API_URL.format(token=self.token, method=method)
        last_err = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if file_path:
                    with open(file_path, "rb") as f:
                        resp = requests.post(
                            url, data=payload, files={file_field: f}, timeout=self.timeout * 3
                        )
                else:
                    resp = requests.post(url, json=payload, timeout=self.timeout)
                data = resp.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
                wait = 2 ** attempt
                log.warning("Lỗi mạng (%s), thử lại sau %ss [%s/%s]", e, wait, attempt, self.max_retries)
                time.sleep(wait)
                continue

            if data.get("ok"):
                return data["result"]

            if resp.status_code == 429:
                wait = data.get("parameters", {}).get("retry_after", 1) + 1
                log.warning("Bị rate limit, đợi %ss", wait)
                time.sleep(wait)
                continue

            raise TelegramError(f"{data.get('error_code')}: {data.get('description')}")

        raise TelegramError(f"Thất bại sau {self.max_retries} lần thử: {last_err}")

    def get_me(self):
        return self._call("getMe")

    def send_message(self, text, parse_mode="HTML", silent=False, reply_markup=None, chat_id=None):
        target = chat_id or self.chat_id
        if not target:
            raise ValueError("Không có chat_id để gửi")
        if len(text) > MAX_LEN:
            text = text[: MAX_LEN - 20] + "\n… (đã cắt bớt)"
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": silent,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def send_document(self, path, caption=""):
        payload = {"chat_id": self.chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
        return self._call("sendDocument", payload, file_field="document", file_path=path)

    def notify(self, level, title, message, service=None, chat_id=None):
        level = level.upper()
        icon = LEVEL_ICON.get(level, "🔔")
        esc = html.escape
        lines = [f"{icon} <b>[{level}] {esc(title)}</b>", ""]
        if service:
            lines.append(f"<b>Service:</b> {esc(service)}")
        lines.append(f"<b>Host:</b> {esc(self.host)}")
        lines.append(f"<b>Time:</b> {datetime.now():%Y-%m-%d %H:%M:%S}")
        lines.append("")
        lines.append(f"<pre>{esc(message)}</pre>")
        silent = level in ("INFO", "SUCCESS")
        return self.send_message("\n".join(lines), silent=silent, chat_id=chat_id)

    def send_survey(self, order_id, service_name="Drive-Thru", chat_id=None):
        order_id = str(order_id)
        if ":" in order_id or len(order_id.encode()) > 30:
            raise ValueError("order_id không được chứa ':' và tối đa 30 byte (giới hạn callback_data 64 byte)")
        esc = html.escape
        text = (
            "⭐ <b>Khảo sát chất lượng dịch vụ Drive-Thru</b>\n\n"
            f"Cảm ơn bạn đã sử dụng <b>{esc(service_name)}</b> (mã đơn <code>#{esc(order_id)}</code>).\n"
            "Bạn hài lòng với dịch vụ ở mức nào? Hãy chọn số sao bên dưới 👇"
        )
        keyboard = {
            "inline_keyboard": [[
                {"text": f"{n}⭐", "callback_data": f"SURVEY:RATE:{order_id}:{n}"}
                for n in range(1, 6)
            ]]
        }
        return self.send_message(text, reply_markup=keyboard, chat_id=chat_id)
