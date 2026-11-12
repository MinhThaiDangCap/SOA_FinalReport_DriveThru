package com.seminar.telebotdemo.handler;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import com.seminar.telebotdemo.survey.SurveyResultStore;
import com.seminar.telebotdemo.survey.NotificationClient;

@Component
public class SurveyHandler {

    private static final Logger log = LoggerFactory.getLogger(SurveyHandler.class);
    public static final String PREFIX = "SURVEY:";

    public record Reply(String text, String buttonLabel, String buttonData) {
        public static Reply of(String text) {
            return new Reply(text, null, null);
        }
    }

    public record CallbackResult(String toast, String editedText, Reply next) {
    }

    private enum Step {
        AWAITING_REASON, AWAITING_FEEDBACK
    }

    private record Session(String orderId, int stars, Step step) {
    }

    private final Map<Long, Session> sessions = new ConcurrentHashMap<>();
    private final Set<String> rated = ConcurrentHashMap.newKeySet();

    private final SurveyResultStore store;
    private final NotificationClient notificationClient;
    private final HttpClient http = HttpClient.newHttpClient();

    @Value("${feedback.url:http://localhost:8002}")
    private String feedbackUrl;

    @Value("${internal.key:change_me_internal_key}")
    private String internalKey;

    public SurveyHandler(SurveyResultStore store, NotificationClient notificationClient) {
        this.store = store;
        this.notificationClient = notificationClient;
    }

    public CallbackResult handleCallback(long chatId, String data) {
        String[] p = data.split(":");
        if (p.length == 4 && "RATE".equals(p[1])) {
            return onRate(chatId, p[2], parseStars(p[3]));
        }
        if (p.length == 3 && "NOFB".equals(p[1])) {
            return onNoFeedback(chatId, p[2]);
        }
        return new CallbackResult("Nút không hợp lệ", null, null);
    }

    private CallbackResult onRate(long chatId, String orderId, int stars) {
        if (stars < 1 || stars > 5) {
            return new CallbackResult("Số sao không hợp lệ", null, null);
        }
        if (!rated.add(chatId + ":" + orderId)) {
            return new CallbackResult("Bạn đã đánh giá đơn này rồi", null, null);
        }

        String edited = "Bạn đã đánh giá đơn " + orderId + ": " + "⭐".repeat(stars) + " (" + stars + "/5)";

        if (stars <= 2) {
            sessions.put(chatId, new Session(orderId, stars, Step.AWAITING_REASON));
            return new CallbackResult("Đã ghi nhận " + stars + "⭐", edited, Reply.of(
                    "Rất tiếc vì trải nghiệm Drive-Thru của bạn chưa tốt.\n"
                            + "Bạn vui lòng cho biết lý do chưa hài lòng để cửa hàng khắc phục ngay nhé:"));
        }

        sessions.put(chatId, new Session(orderId, stars, Step.AWAITING_FEEDBACK));
        return new CallbackResult("Đã ghi nhận " + stars + "⭐", edited, new Reply(
                "Cảm ơn bạn đã hài lòng với dịch vụ Drive-Thru!\n"
                        + "Bạn có muốn góp ý gì thêm không? Nhắn bên dưới hoặc bấm nút nếu không có.",
                "Không, cảm ơn", PREFIX + "NOFB:" + orderId));
    }

    private CallbackResult onNoFeedback(long chatId, String orderId) {
        Session s = sessions.get(chatId);
        if (s == null || !s.orderId().equals(orderId) || s.step() != Step.AWAITING_FEEDBACK) {
            return new CallbackResult("Khảo sát đã hoàn tất", "Khảo sát này đã hoàn tất.", null);
        }
        sessions.remove(chatId);
        return new CallbackResult("Đã ghi nhận", "Bạn không có góp ý thêm.", Reply.of(finish(chatId, s, null)));
    }

    public boolean hasPending(long chatId) {
        return sessions.containsKey(chatId);
    }

    public String handleText(long chatId, String text) {
        Session s = sessions.remove(chatId);
        if (s == null) {
            return "Hiện không có khảo sát nào đang chờ.";
        }
        return finish(chatId, s, text.trim());
    }

    public String skip(long chatId) {
        Session s = sessions.remove(chatId);
        if (s == null) {
            return "Hiện không có khảo sát nào đang chờ.";
        }
        return finish(chatId, s, "Khách bỏ qua nhập lý do");
    }

    private String finish(long chatId, Session s, String comment) {
        store.save(chatId, s.orderId(), s.stars(), comment);

        // Chuyển kết quả khảo sát sang feedback-service để lưu vào PostgreSQL (feedback_db)
        syncToFeedbackService(s.orderId(), s.stars(), comment);

        if (s.stars() <= 2) {
            notificationClient.send("feedback-service", "WARNING", "Khách chưa hài lòng (Telegram)",
                    "Chat " + chatId + " chấm " + s.stars() + "/5 cho đơn " + s.orderId()
                            + (comment == null ? " (không nêu lý do)" : "\nLý do: " + comment));
            return "Cảm ơn bạn đã chia sẻ. Quản lý cửa hàng đã nhận được phản hồi và sẽ cải thiện chất lượng ngay!";
        }
        return "💙 Cảm ơn bạn đã đánh giá! Đánh giá của bạn đã được lưu lên hệ thống Drive-Thru.";
    }

    private void syncToFeedbackService(String rawOrderId, int stars, String comment) {
        try {
            // Trích xuất mã số đơn hàng (ví dụ "ORD-1001" -> 1001)
            String digits = rawOrderId.replaceAll("[^0-9]", "");
            int orderId = digits.isEmpty() ? Math.abs(rawOrderId.hashCode() % 100000) : Integer.parseInt(digits);

            String safeComment = comment == null ? "" : comment.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
            String body = "{\"order_id\":" + orderId
                    + ",\"customer_id\":1"
                    + ",\"station_id\":1"
                    + ",\"rating\":" + stars
                    + ",\"comment\":\"" + safeComment + "\"}";

            HttpRequest req = HttpRequest.newBuilder(URI.create(feedbackUrl + "/internal/reviews/telegram"))
                    .timeout(Duration.ofSeconds(5))
                    .header("Content-Type", "application/json; charset=utf-8")
                    .header("X-Internal-Key", internalKey)
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();

            http.sendAsync(req, HttpResponse.BodyHandlers.ofString())
                    .whenComplete((resp, err) -> {
                        if (err != null) {
                            log.warn("Không gửi được kết quả sang feedback-service: {}", err.getMessage());
                        } else {
                            log.info("Đã đồng bộ đánh giá đơn #{} sang feedback-service (HTTP {})", orderId, resp.statusCode());
                        }
                    });
        } catch (Exception e) {
            log.warn("Lỗi đồng bộ sang feedback-service: {}", e.getMessage());
        }
    }

    private static int parseStars(String raw) {
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException e) {
            return -1;
        }
    }
}
