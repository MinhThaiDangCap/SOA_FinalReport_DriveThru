package com.seminar.telebotdemo.survey;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class CustomerStore {

    private static final Logger log = LoggerFactory.getLogger(CustomerStore.class);
    private static final Path FILE = Path.of("data", "customers.csv");
    private static final String HEADER = "code,chat_id,name,username,registered_at\n";

    /** Lưu khách nếu chưa có, trả về mã khách (đã có thì trả mã cũ). */
    public synchronized String register(long chatId, String name, String username) {
        try {
            Files.createDirectories(FILE.getParent());
            if (Files.notExists(FILE)) {
                Files.writeString(FILE, HEADER, StandardCharsets.UTF_8, StandardOpenOption.CREATE);
            }
            List<String> lines = Files.readAllLines(FILE, StandardCharsets.UTF_8);
            Set<String> codes = new HashSet<>();
            for (int i = 1; i < lines.size(); i++) {
                String[] p = lines.get(i).split(",", -1);
                if (p.length < 2) continue;
                if (p[1].equals(String.valueOf(chatId))) {
                    return p[0];                       // khách cũ
                }
                codes.add(p[0]);
            }
            int n = lines.size();                      // dòng header tính là 1 => KH001 cho khách đầu tiên
            String code = String.format("KH%03d", n);
            while (codes.contains(code)) {
                code = String.format("KH%03d", ++n);
            }
            String line = String.join(",", code, String.valueOf(chatId), clean(name), clean(username),
                    LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)) + "\n";
            Files.writeString(FILE, line, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
            log.info("Khách mới: {} -> chatId={}", code, chatId);
            return code;
        } catch (IOException e) {
            log.error("Không ghi được {}", FILE, e);
            return null;
        }
    }

    private static String clean(String s) {
        return s == null ? "" : s.replaceAll("[,\\r\\n]", " ").trim();
    }
}