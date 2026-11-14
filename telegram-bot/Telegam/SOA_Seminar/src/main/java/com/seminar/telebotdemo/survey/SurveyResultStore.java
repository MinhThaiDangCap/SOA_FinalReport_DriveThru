package com.seminar.telebotdemo.survey;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class SurveyResultStore {

    private static final Logger log = LoggerFactory.getLogger(SurveyResultStore.class);
    private static final Path FILE = Path.of("data", "survey_results.csv");
    private static final String HEADER = "time,chat_id,order_id,stars,sentiment,comment\n";

    public synchronized void save(long chatId, String orderId, int stars, String comment) {
        String sentiment = stars <= 2 ? "UNSATISFIED" : "SATISFIED";
        String line = String.join(",",
                LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME),
                String.valueOf(chatId),
                csv(orderId),
                String.valueOf(stars),
                sentiment,
                csv(comment == null ? "" : comment)) + "\n";
        try {
            Files.createDirectories(FILE.getParent());
            if (Files.notExists(FILE)) {
                Files.writeString(FILE, HEADER, StandardCharsets.UTF_8, StandardOpenOption.CREATE);
            }
            Files.writeString(FILE, line, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
            log.info("Đã lưu khảo sát: order={}, stars={}, sentiment={}", orderId, stars, sentiment);
        } catch (IOException e) {
            log.error("Không ghi được {}", FILE, e);
        }
    }

    private static String csv(String value) {
        return "\"" + value.replace("\"", "\"\"").replace("\r", " ").replace("\n", " ") + "\"";
    }
}
