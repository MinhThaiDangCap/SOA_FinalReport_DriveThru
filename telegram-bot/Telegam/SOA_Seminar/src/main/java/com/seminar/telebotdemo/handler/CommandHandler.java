package com.seminar.telebotdemo.handler;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class CommandHandler {

    private static final Logger log = LoggerFactory.getLogger(CommandHandler.class);

    private final SurveyHandler surveyHandler;
    private final HttpClient http = HttpClient.newHttpClient();

    @Value("${auth.url:http://localhost:8001}")
    private String authUrl;

    @Value("${internal.key:change_me_internal_key}")
    private String internalKey;

    public CommandHandler(SurveyHandler surveyHandler) {
        this.surveyHandler = surveyHandler;
    }

    public String handle(long chatId, String command) {
        String[] parts = command.trim().split("\\s+", 2);
        String base = parts[0].toLowerCase();

        return switch (base) {
            case "/start" -> {
                if (parts.length > 1 && !parts[1].isBlank()) {
                    yield bindAccountWithAuthService(chatId, parts[1].trim());
                }
                yield "Xin chào! Mình là Bot trợ lý Drive-Thru.\n"
                        + "• Để liên kết tài khoản web, hãy bấm nút 'Kết nối Telegram' trên trang web Drive-Thru.\n"
                        + "• Gõ /help để xem danh sách lệnh hỗ trợ.";
            }
            case "/help" -> "Danh sách lệnh hỗ trợ:\n"
                    + "/start - Khởi động bot / Liên kết tài khoản\n"
                    + "/status - Kiểm tra trạng thái hệ thống\n"
                    + "/skip - Bỏ qua câu hỏi khảo sát đang chờ";
            case "/status" -> "Hệ thống Bot Drive-Thru đang hoạt động bình thường \uD83D\uDFE2";
            case "/skip" -> surveyHandler.skip(chatId);
            default -> "Lệnh không hợp lệ. Vui lòng gõ /help.";
        };
    }

    private String bindAccountWithAuthService(long chatId, String token) {
        try {
            String body = "{\"token\":\"" + token.replace("\"", "") + "\",\"chat_id\":\"" + chatId + "\"}";
            HttpRequest request = HttpRequest.newBuilder(URI.create(authUrl + "/internal/auth/telegram/bind"))
                    .timeout(Duration.ofSeconds(5))
                    .header("Content-Type", "application/json; charset=utf-8")
                    .header("X-Internal-Key", internalKey)
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();

            HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) {
                log.info("Đã liên kết thành công chatId={} với token={}", chatId, token);
                return "✅ Liên kết tài khoản Drive-Thru thành công!\n"
                        + "Từ bây giờ, bạn sẽ nhận được thông báo khi đơn hàng xác nhận, khi món ăn sẵn sàng và phiếu đánh giá dịch vụ ngay tại đây.";
            } else {
                log.warn("Liên kết thất bại (HTTP {}): {}", response.statusCode(), response.body());
                return "⚠️ Mã liên kết không hợp lệ hoặc đã hết hạn. Vui lòng bấm lại nút 'Kết nối Telegram' trên web.";
            }
        } catch (Exception e) {
            log.error("Lỗi khi gọi auth-service để bind Telegram: {}", e.getMessage());
            return "⚠️ Không thể kết nối tới Auth Service lúc này. Vui lòng thử lại sau.";
        }
    }
}
