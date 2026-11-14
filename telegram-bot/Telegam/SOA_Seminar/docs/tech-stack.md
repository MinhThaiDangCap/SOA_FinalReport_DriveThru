# Công nghệ sử dụng — Telegram Bot API Seminar

## Ngôn ngữ & Nền tảng
| Công nghệ | Version | Vai trò |
|---|---|---|
| Java | 17 (LTS) | Ngôn ngữ chính |
| Spring Boot | 4.1.1 | Framework xây dựng microservice |
| Maven | (Maven Wrapper `mvnw`) | Quản lý dependency & build project |

## Thư viện chính
| Thư viện | Version | Vai trò |
|---|---|---|
| `spring-boot-starter-webmvc` | theo Spring Boot 4.1.1 | Xây REST/web layer cho microservice |
| `org.telegram:telegrambots-spring-boot-starter` | 6.9.7.1 | Wrapper Java cho Telegram Bot API — cung cấp `TelegramLongPollingBot`, `SendMessage`, xử lý update tự động |
| `me.paulschwarz:spring-dotenv` | 4.0.0 | Đọc biến môi trường (token, username) từ file `.env`, tránh hardcode thông tin nhạy cảm |

## Công nghệ nền (Telegram)
| Thành phần | Ghi chú |
|---|---|
| Telegram Bot API | REST API miễn phí của Telegram để tạo và điều khiển bot |
| Long Polling | Cơ chế lấy update — app tự động hỏi Telegram server có tin mới không (chọn thay vì Webhook vì không cần HTTPS/domain public, phù hợp demo local) |
| @BotFather | Bot chính thức của Telegram dùng để tạo bot, lấy token, cấu hình |

## Công cụ phát triển
| Công cụ | Vai trò |
|---|---|
| Visual Studio Code + Extension Pack for Java + Spring Boot Extension Pack | IDE viết, chạy, debug code |
| Git & GitHub | Quản lý phiên bản, làm việc nhóm |
| Eclipse Temurin JDK 17 | Bộ JDK dùng để biên dịch & chạy project |
