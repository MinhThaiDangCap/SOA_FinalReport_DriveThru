package com.seminar.telebotdemo.survey;

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
public class NotificationClient {

    private static final Logger log = LoggerFactory.getLogger(NotificationClient.class);

    private final HttpClient http = HttpClient.newHttpClient();

    @Value("${notification.url}")
    private String baseUrl;

    @Value("${notification.api-key}")
    private String apiKey;

    public void send(String service, String level, String title, String message) {
        String body = "{\"service\":" + quote(service)
                + ",\"level\":" + quote(level)
                + ",\"title\":" + quote(title)
                + ",\"message\":" + quote(message) + "}";
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + "/notify"))
                .timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json; charset=utf-8")
                .header("X-API-Key", apiKey)
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        http.sendAsync(request, HttpResponse.BodyHandlers.discarding())
                .whenComplete((resp, err) -> {
                    if (err != null) {
                        log.warn("Không gọi được Notification Service: {}", err.getMessage());
                    } else if (resp.statusCode() != 202) {
                        log.warn("Notification Service trả về HTTP {}", resp.statusCode());
                    } else {
                        log.info("Đã gửi cảnh báo qua Notification Service");
                    }
                });
    }

    private static String quote(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        return sb.append('"').toString();
    }
}
