# SOA Seminar – Telegram Bot API

Seminar môn SOA: Telegram Bot API gồm 3 chức năng, mỗi chức năng nằm ở một chỗ riêng.

| # | Chức năng | Vị trí | Công nghệ |
|---|-----------|--------|-----------|
| 1 | Command Handling (`/start`, `/help`, `/status`, `/skip`) | `src/.../handler/CommandHandler.java` | Spring Boot |
| 2 | Chatbot Basics (trả lời tin nhắn thường, hội thoại khảo sát, tự lưu khách) | `ChatResponder.java`, `SurveyHandler.java`, `CustomerStore.java` | Spring Boot |
| 3 | System Notifications (cảnh báo CPU/RAM/Disk, REST `/notify`, `/survey`) | `notification-service/` | Python + FastAPI |

## Flow demo: Post-sale Survey

Sau khi dùng xong dịch vụ, bot **chủ động** gửi phiếu khảo sát 5 sao tới khách (không cần gõ `/start`):

- Chấm **≤ 2 sao** (không hài lòng): bot hỏi lý do, lưu kết quả và cảnh báo đội CSKH qua Telegram.
- Chấm **≥ 3 sao** (hài lòng): bot hỏi khách có muốn góp ý gì không, rồi lưu kết quả.
- Gõ `/skip` để bỏ qua câu hỏi lý do / góp ý (số sao vẫn được lưu).

**Quản lý khách hàng:** mỗi người nhắn bot lần đầu sẽ được bot tự lưu vào `data/customers.csv` và cấp một **mã khách** (`KH001`, `KH002`, ...). Telegram bot không gửi được theo số điện thoại mà chỉ gửi theo `chat_id`, nên mã khách đóng vai trò thay thế. Khi gửi khảo sát chỉ cần chỉ định mã khách, có thể gửi cho một người, nhiều người hoặc tất cả.

## Cấu trúc thư mục

```
SOA_Seminar/
├── src/main/java/com/seminar/telebotdemo/
│   ├── TelebotdemoApplication.java
│   ├── bot/MyTelegramBot.java          # nhận update + điều hướng + gửi tin + lưu khách
│   ├── config/TelegramBotConfig.java   # đăng ký bot
│   ├── handler/
│   │   ├── CommandHandler.java         # xử lý lệnh "/" (có /skip)
│   │   ├── ChatResponder.java          # chat thường
│   │   └── SurveyHandler.java          # máy trạng thái khảo sát sau bán
│   └── survey/
│       ├── CustomerStore.java          # lưu khách + cấp mã khách -> data/customers.csv
│       ├── SurveyResultStore.java      # lưu kết quả -> data/survey_results.csv
│       └── NotificationClient.java     # gọi REST /notify để cảnh báo CSKH
├── src/assembly/
│   ├── distribution.xml                # quy định nội dung file zip phân phối (Maven)
│   └── HUONG_DAN_CHAY.txt              # hướng dẫn chạy, nằm trong zip phân phối
├── notification-service/               # System Notification (Python)
│   ├── notifier.py                     # thư viện gửi Telegram (retry, 429, cắt 4096 ký tự)
│   ├── notification_service.py         # REST: POST /notify, POST /survey, GET /health
│   ├── customers.py                    # đọc data/customers.csv (mã khách -> chat_id)
│   ├── monitor.py                      # giám sát tài nguyên
│   ├── trigger_survey.py               # gửi phiếu khảo sát (--list, --to, --all)
│   ├── get_chat_id.py                  # (không còn cần thiết, bot đã tự lưu chat_id)
│   └── requirements.txt
├── data/                               # tự tạo khi chạy, không nằm trong Git
│   ├── customers.csv                   # danh sách khách + mã khách
│   └── survey_results.csv              # kết quả khảo sát
├── docs/
│   ├── tech-stack.md
│   └── python-notification-guide.txt
├── pom.xml                             # cấu hình Maven: thư viện, plugin, đóng gói
├── mvnw, mvnw.cmd, .mvn/               # Maven Wrapper (không cần cài Maven)
└── .env.example                        # mẫu cấu hình (không chứa token thật)
```

## Yêu cầu

- **Java JDK 17 trở lên** (kiểm tra: `java -version`). Biến `JAVA_HOME` phải trỏ tới *thư mục* JDK, không phải file `java.exe`.
- **Python 3.9 trở lên** (kiểm tra: `python --version`).
- Một **bot Telegram riêng** của bạn, tạo bằng `@BotFather`. Không dùng chung token với người khác, vì Telegram sẽ báo lỗi 409.

## Cách 1: tải bản build sẵn (chỉ muốn chạy thử)

1. Vào mục [Releases](https://github.com/Volker06/SOA_Seminar/releases) và tải **`SOA_Seminar-dist.zip`**.
2. Giải nén, làm theo file `HUONG_DAN_CHAY.txt` bên trong.

Không cần cài Maven, chỉ cần Java 17 trở lên và Python.

## Cách 2: clone code và tự build (muốn sửa, dùng lại code)

**Bước 1. Clone**

```
git clone https://github.com/Volker06/SOA_Seminar.git
cd SOA_Seminar
```

**Bước 2. Tạo file `.env`** (không commit file này)

```
copy .env.example .env        (Windows)
cp .env.example .env          (Mac/Linux)
```

Điền các biến sau:

| Biến | Ý nghĩa |
|---|---|
| `BOT_TOKEN`, `TELEGRAM_BOT_TOKEN` | Token bot từ `@BotFather` (hai biến cùng một giá trị) |
| `BOT_USERNAME` | Username của bot |
| `TELEGRAM_CHAT_ID` | chat_id của quản trị/CSKH: nhận cảnh báo khi khách chấm thấp điểm, và là nơi nhận phiếu khi gửi thử mà không chỉ định khách. Mở bot trên Telegram, bấm **Start** một lần, rồi nhắn `@userinfobot` để biết |
| `SERVICE_API_KEY` | Khóa bí mật cho REST của Notification Service, tự đặt |
| `NOTIFICATION_URL` | (Tuỳ chọn) Địa chỉ Notification Service, mặc định `http://localhost:8000` |
| `CUSTOMERS_FILE` | (Tuỳ chọn) Đường dẫn tới `customers.csv` nếu để khác chỗ mặc định |

**Bước 3. Build bằng Maven**

```
mvnw.cmd clean package -DskipTests        (Windows)
./mvnw clean package -DskipTests          (Mac/Linux)
```

Lần đầu Maven tải thư viện nên cần có mạng. `-DskipTests` bỏ qua bài test mặc định (bài này cần cấu hình token để khởi động ứng dụng). Kết quả nằm trong thư mục `target/`:

| File | Là gì |
|---|---|
| `target/telebotdemo-0.0.1-SNAPSHOT.jar` | Bot Java đã gói sẵn thư viện, chạy bằng `java -jar` |
| `target/SOA_Seminar-dist.zip` | Gói phân phối: JAR + `notification-service/` + `.env.example` + hướng dẫn |

Muốn chạy thử ngay mà không tạo JAR: `mvnw.cmd spring-boot:run`.

**Bước 4. Chạy bot Java và Notification Service (2 cửa sổ terminal)**

```
# Terminal 1: bot Java (đứng ở thư mục có file .env, giữ mở suốt quá trình demo)
java -jar target/telebotdemo-0.0.1-SNAPSHOT.jar

# Terminal 2: Notification Service
cd notification-service
pip install -r requirements.txt
uvicorn notification_service:app --port 8000
```

Notification Service dùng để bot Java gửi cảnh báo tới CSKH khi khách chấm ≤ 2 sao.

**Bước 5. Thu thập khách hàng (làm trên Telegram)**

Mỗi khách (hoặc mỗi tài khoản Telegram dùng để thử) mở bot và nhắn `/start`. Bot trả lời kèm mã khách:

```
Mã khách hàng của bạn: KH001
```

Người thứ hai là `KH002`, người thứ ba là `KH003`, và cứ thế tiếp tục. Một người nhắn nhiều lần vẫn chỉ có một mã. Bot tự ghi vào `data/customers.csv`:

```
code,chat_id,name,username,registered_at
KH001,123456789,Nguyen Van A,vana,2026-10-14T10:00:00
```

Có thể mở file này để kiểm tra, hoặc sửa cột `code` thành tên dễ nhớ (vd: `AN`, `BINH`).

**Bước 6. Gửi phiếu khảo sát (Terminal 3)**

```
cd notification-service

# Xem danh sách khách đã lưu
python trigger_survey.py --list

# Gửi cho 1 khách
python trigger_survey.py --order ORD-1001 --service "Giặt ủi" --to KH001

# Gửi cho nhiều khách (cách nhau bằng dấu cách)
python trigger_survey.py --order ORD-1001 --service "Giặt ủi" --to KH001 KH002

# Gửi cho tất cả khách đã lưu
python trigger_survey.py --order ORD-1001 --service "Giặt ủi" --all

# Không chỉ định khách: gửi về TELEGRAM_CHAT_ID của bạn (test nhanh)
python trigger_survey.py --order ORD-1001 --service "Giặt ủi"
```

| Tham số | Ý nghĩa |
|---|---|
| `--order` | Mã đơn hàng. Khi gửi nhiều khách, tự thêm mã khách phía sau (vd: `ORD-1001-KH001`) để phân biệt trong kết quả |
| `--service` | Tên dịch vụ khách vừa dùng |
| `--to MÃ [MÃ ...]` | Gửi cho các khách chỉ định |
| `--all` | Gửi cho toàn bộ khách đã lưu |
| `--list` | Xem danh sách khách đã lưu |
| `--delay N` | Chờ N giây trước khi gửi |

Nếu một khách chặn bot hoặc bị lỗi, chương trình báo lỗi riêng người đó rồi gửi tiếp cho những người còn lại.

Kết quả khảo sát được ghi vào `data/survey_results.csv` (cột `chat_id` đối chiếu được với `data/customers.csv`). Muốn bật thêm giám sát tài nguyên: `python monitor.py`.

## Maven dùng để làm gì

Maven chỉ phục vụ **phần Java**, ở bước build và đóng gói, không chạy khi bot hoạt động.

| Thành phần | Vai trò |
|---|---|
| `pom.xml` | Khai báo Java 17, thư viện (Spring Boot, telegrambots, spring-dotenv) và plugin |
| `spring-boot-maven-plugin` | Gói code và thư viện thành một file JAR chạy được |
| `maven-assembly-plugin` + `src/assembly/distribution.xml` | Gom JAR cùng `notification-service/` thành `SOA_Seminar-dist.zip` |
| `mvnw`, `mvnw.cmd`, `.mvn/` | Maven Wrapper: chạy Maven mà không cần cài sẵn |

Thư mục `target/` (kết quả build) **không nằm trong Git**. Mỗi người tự tạo lại bằng lệnh ở Bước 3. Phần Python không được Maven xử lý, Maven chỉ chép thư mục `notification-service/` vào gói zip.

## Dùng lại và mở rộng

| Muốn đổi | Sửa file |
|---|---|
| Nội dung phiếu khảo sát, số nút sao | `notification-service/notifier.py` (hàm `send_survey`) |
| Luồng hỏi lý do / góp ý | `handler/SurveyHandler.java` |
| Thêm lệnh `/...` | `handler/CommandHandler.java` |
| Cách lưu kết quả khảo sát (CSV sang database) | `survey/SurveyResultStore.java` |
| Cách lưu khách / quy tắc đặt mã khách | `survey/CustomerStore.java` và `notification-service/customers.py` |
| Kích hoạt khảo sát từ hệ thống khác | `POST /survey` trong `notification_service.py` (header `X-API-Key`) |

Thêm chức năng mới: tạo một class `@Component` trong `handler/` rồi gọi nó từ `MyTelegramBot.onUpdateReceived`.

## Lưu ý

- **Không commit `.env`** (chứa token bot). Nếu lỡ lộ token, vào `@BotFather` dùng `/revoke` để đổi.
- Telegram chỉ cho bot nhắn trước với người **đã bấm Start ít nhất một lần**. Người đã nhắn bot từ trước khi có tính năng lưu khách cần nhắn lại 1 lần để được lưu.
- Thư mục `data/` nằm trong `.gitignore`. Muốn xóa sạch để demo lại từ đầu, xóa `data/customers.csv` và `data/survey_results.csv`.
- Python mặc định đọc `data/customers.csv` ở thư mục cha của `notification-service` (cùng chỗ với file `.jar`). Nếu để khác chỗ, đặt `CUSTOMERS_FILE` trong `.env`.
- Trạng thái hội thoại khảo sát lưu trong RAM nên restart bot thì mất phiên đang dở. Kết quả lưu CSV chỉ để demo.
- `get_chat_id.py` không còn cần dùng vì bot đã tự lưu `chat_id`. Nếu chạy mà báo lỗi 409, hãy tắt bot Java trước (cả hai cùng dùng `getUpdates`).