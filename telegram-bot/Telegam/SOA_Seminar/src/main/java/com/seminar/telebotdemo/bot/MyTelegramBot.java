package com.seminar.telebotdemo.bot;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.updatingmessages.EditMessageText;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import com.seminar.telebotdemo.handler.ChatResponder;
import com.seminar.telebotdemo.handler.CommandHandler;
import com.seminar.telebotdemo.handler.SurveyHandler;
import com.seminar.telebotdemo.survey.CustomerStore;

@Component
@SuppressWarnings("deprecation")
public class MyTelegramBot extends TelegramLongPollingBot {

    private static final Logger log = LoggerFactory.getLogger(MyTelegramBot.class);

    private final CommandHandler commandHandler;
    private final ChatResponder chatResponder;
    private final SurveyHandler surveyHandler;
    private final CustomerStore customerStore;

    public MyTelegramBot(CommandHandler commandHandler, ChatResponder chatResponder,
                         SurveyHandler surveyHandler, CustomerStore customerStore) {
        this.commandHandler = commandHandler;
        this.chatResponder = chatResponder;
        this.surveyHandler = surveyHandler;
        this.customerStore = customerStore;
    }

    @Value("${telegram.bot.username}")
    private String botUsername;

    @Value("${telegram.bot.token}")
    private String botToken;


    @Override
    public String getBotUsername() {
        return botUsername;
    }

    @Override
    public String getBotToken() {
        return botToken;
    }

    @Override
    public void onUpdateReceived(Update update) {
        if (update.hasCallbackQuery()) {
            onCallback(update.getCallbackQuery());
            return;
        }
        if (!update.hasMessage() || !update.getMessage().hasText()) {
            return;
        }
        String text = update.getMessage().getText();
long chatId = update.getMessage().getChatId();

// Lưu khách (nếu chưa có) mỗi khi có người nhắn tin
String code = null;
var from = update.getMessage().getFrom();
if (from != null) {
    String fullName = ((from.getFirstName() == null ? "" : from.getFirstName()) + " "
            + (from.getLastName() == null ? "" : from.getLastName())).trim();
    code = customerStore.register(chatId, fullName, from.getUserName());
}

    String reply;
    if (text.startsWith("/")) {
        reply = commandHandler.handle(chatId, text);
    if (text.toLowerCase().startsWith("/start") && code != null) {
        reply += "\nMã khách hàng của bạn: " + code;
    }
    } else if (surveyHandler.hasPending(chatId)) {
        reply = surveyHandler.handleText(chatId, text);
    } else {
        reply = chatResponder.respond(text);
    }
        sendReply(chatId, reply);}

    private void onCallback(CallbackQuery cb) {
        String data = cb.getData();
        if (data == null || !data.startsWith(SurveyHandler.PREFIX) || cb.getMessage() == null) {
            answerCallback(cb.getId(), null);
            return;
        }
        long chatId = cb.getMessage().getChatId();
        int messageId = cb.getMessage().getMessageId();

        SurveyHandler.CallbackResult result = surveyHandler.handleCallback(chatId, data);
        answerCallback(cb.getId(), result.toast());
        if (result.editedText() != null) {
            editMessage(chatId, messageId, result.editedText());
        }
        if (result.next() != null) {
            sendReply(chatId, result.next());
        }
    }

    private void sendReply(long chatId, String text) {
        SendMessage message = new SendMessage(String.valueOf(chatId), text);
        try {
            execute(message);
        } catch (TelegramApiException e) {
            log.error("Gửi tin nhắn thất bại (chatId={})", chatId, e);
        }
    }

    private void sendReply(long chatId, SurveyHandler.Reply reply) {
        if (reply.buttonLabel() == null) {
            sendReply(chatId, reply.text());
            return;
        }
        InlineKeyboardButton button = InlineKeyboardButton.builder()
                .text(reply.buttonLabel())
                .callbackData(reply.buttonData())
                .build();
        SendMessage message = SendMessage.builder()
                .chatId(String.valueOf(chatId))
                .text(reply.text())
                .replyMarkup(InlineKeyboardMarkup.builder().keyboard(List.of(List.of(button))).build())
                .build();
        try {
            execute(message);
        } catch (TelegramApiException e) {
            log.error("Gửi tin nhắn có nút thất bại (chatId={})", chatId, e);
        }
    }

    private void editMessage(long chatId, int messageId, String text) {
        EditMessageText edit = EditMessageText.builder()
                .chatId(String.valueOf(chatId))
                .messageId(messageId)
                .text(text)
                .build();
        try {
            execute(edit);
        } catch (TelegramApiException e) {
            log.error("Sửa tin nhắn thất bại (chatId={}, messageId={})", chatId, messageId, e);
        }
    }

    private void answerCallback(String callbackId, String toast) {
        AnswerCallbackQuery answer = AnswerCallbackQuery.builder()
                .callbackQueryId(callbackId)
                .text(toast)
                .build();
        try {
            execute(answer);
        } catch (TelegramApiException e) {
            log.error("Trả lời callback thất bại", e);
        }
    }

}
