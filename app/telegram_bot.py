import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from app.config import settings
from app.security import validate_and_sanitize_input
from app.ai_service import generate_chat_response
from app.vocab_service import lookup_vocabulary
from app.database import save_message

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Chào mừng bạn đến với **Study Bot - Trợ lý học tập**!\n\n"
        "📚 Các chức năng chính:\n"
        "• Gửi bất kỳ câu hỏi học tập nào để được giải thích chi tiết từng bước.\n"
        "• Dùng lệnh `/vocab <từ>` để tra cứu từ vựng (nghĩa, IPA, ví dụ, từ đồng nghĩa).\n"
        "• Dùng lệnh `/level <beginner|intermediate|advanced>` để đổi cấp độ giải thích.\n"
        "• Dùng lệnh `/help` để xem hướng dẫn.\n"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in settings.VALID_LEVELS:
        valid_str = " | ".join(settings.VALID_LEVELS)
        await update.message.reply_text(
            f"Vui lòng chọn cấp độ hợp lệ: `{valid_str}`.\nVí dụ: `/level intermediate`",
            parse_mode="Markdown"
        )
        return
        
    new_level = context.args[0].lower()
    context.user_data["level"] = new_level
    await update.message.reply_text(
        f"✅ Đã đổi cấp độ học tập thành: **{new_level.capitalize()}**!",
        parse_mode="Markdown"
    )

async def vocab_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Vui lòng nhập từ cần tra. Ví dụ: `/vocab achieve`", parse_mode="Markdown")
        return
        
    raw_word = " ".join(context.args)
    is_safe, word, err_msg = validate_and_sanitize_input(raw_word)
    if not is_safe:
        await update.message.reply_text(f"⚠️ {err_msg}")
        return

    chat_id = str(update.effective_chat.id)
    level = context.user_data.get("level", "beginner")
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    res = lookup_vocabulary(word, language="vi", level=level)
    
    meanings_str = "\n".join([f"• {m}" for m in res.get("meanings", [])]) or "Đang cập nhật"
    examples_str = "\n".join([f"• {e}" for e in res.get("examples", [])]) or "Đang cập nhật"
    synonyms_str = ", ".join(res.get("synonyms", [])) or "Không có"
    antonyms_str = ", ".join(res.get("antonyms", [])) or "Không có"
    
    reply = (
        f"📖 **Từ vựng:** `{res.get('word')}`\n"
        f"🏷 **Từ loại:** {res.get('part_of_speech')}\n"
        f"🗣 **Phiên âm:** `{res.get('phonetic')}`\n\n"
        f"💡 **Ý nghĩa tiếng Việt:**\n{meanings_str}\n\n"
        f"📝 **Ví dụ minh họa:**\n{examples_str}\n\n"
        f"🔄 **Đồng nghĩa:** {synonyms_str}\n"
        f"⚡ **Trái nghĩa:** {antonyms_str}"
    )
    
    save_message(f"tg_{chat_id}", "user", f"/vocab {word}", msg_type="vocab")
    save_message(f"tg_{chat_id}", "bot", reply, msg_type="vocab")
    
    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = str(update.effective_chat.id)
    
    is_safe, cleaned_text, err_msg = validate_and_sanitize_input(text)
    if not is_safe:
        await update.message.reply_text(f"⚠️ {err_msg}")
        return
        
    level = context.user_data.get("level", "beginner")
    
    # Báo đang gõ
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    messages = [{"role": "user", "content": cleaned_text}]
    response_data = generate_chat_response(messages, level=level)
    answer = response_data.get("answer", "Xin lỗi, không nhận được phản hồi.")
    
    # Lưu vào database
    save_message(f"tg_{chat_id}", "user", cleaned_text)
    save_message(f"tg_{chat_id}", "bot", answer)
    
    await update.message.reply_text(answer)

def run_telegram_bot():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("Chưa cấu hình TELEGRAM_BOT_TOKEN trong .env. Telegram bot sẽ không khởi chạy.")
        return
        
    logging.basicConfig(level=logging.INFO)
    logger.info("Khởi động Telegram Bot...")
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("vocab", vocab_command))
    app.add_handler(CommandHandler("level", level_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == "__main__":
    run_telegram_bot()
