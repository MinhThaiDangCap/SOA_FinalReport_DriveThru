import argparse
import logging
import time

import customers
from notifier import TelegramError, TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    ap = argparse.ArgumentParser(description="Gửi phiếu khảo sát sau bán qua Telegram")
    ap.add_argument("--order", default=f"ORD-{int(time.time()) % 100000}", help="Mã đơn hàng")
    ap.add_argument("--service", default="Dịch vụ demo", help="Tên dịch vụ khách vừa dùng")
    ap.add_argument("--delay", type=int, default=0, help="Số giây chờ trước khi gửi")
    ap.add_argument("--to", nargs="+", metavar="MÃ", help="Mã khách, ví dụ: KH001 KH002")
    ap.add_argument("--all", action="store_true", help="Gửi cho toàn bộ khách đã lưu")
    ap.add_argument("--list", action="store_true", help="Xem danh sách khách đã lưu")
    args = ap.parse_args()

    book = customers.load()

    if args.list:
        if not book:
            raise SystemExit("Chưa có khách nào. Hãy nhắn cho bot (/start) trước.")
        for code, c in book.items():
            print(f"{code}  chat_id={c['chat_id']}  {c['name']}  @{c['username']}")
        return

    # Xác định danh sách người nhận: (mã, chat_id)
    if args.all:
        targets = [(code, c["chat_id"]) for code, c in book.items()]
    elif args.to:
        targets = []
        for code in (x.upper() for x in args.to):
            if code in book:
                targets.append((code, book[code]["chat_id"]))
            else:
                print(f"Bỏ qua {code}: không có trong danh sách khách")
    else:
        targets = [("ADMIN", None)]   # không chỉ định -> gửi về TELEGRAM_CHAT_ID như cũ

    if not targets:
        raise SystemExit("Không có người nhận hợp lệ.")

    notifier = TelegramNotifier()
    if args.delay:
        print(f"Dịch vụ đang thực hiện... gửi khảo sát sau {args.delay}s")
        time.sleep(args.delay)

    ok = 0
    for code, chat_id in targets:
        order_id = args.order if len(targets) == 1 else f"{args.order}-{code}"
        try:
            notifier.send_survey(order_id, args.service, chat_id=chat_id)
            print(f"✔ Đã gửi cho {code} (đơn {order_id})")
            ok += 1
        except (TelegramError, ValueError) as e:
            print(f"✘ Gửi cho {code} thất bại: {e}")   # lỗi 1 người không làm dừng cả loạt
        time.sleep(0.1)

    print(f"Xong: {ok}/{len(targets)} thành công.")


if __name__ == "__main__":
    main()