import logging
import asyncio
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from app.config import settings
from app.security import validate_and_sanitize_input
from app.ai_service import generate_chat_response
from app.vocab_service import lookup_vocabulary
from app.database import save_message

logger = logging.getLogger(__name__)

# Bàn phím nút bấm nhanh cố định dưới màn hình
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📖 Tra từ vựng", "🌐 Dịch câu"],
        ["🎯 Đổi cấp độ", "❓ Hướng dẫn"]
    ],
    resize_keyboard=True
)

def get_level_inline_keyboard(current_level: str = "beginner") -> InlineKeyboardMarkup:
    levels = [
        ("beginner", "🟢 Cơ bản (Beginner)"),
        ("intermediate", "🟡 Trung cấp (Intermediate)"),
        ("advanced", "🔴 Nâng cao (Advanced)")
    ]
    keyboard = []
    for code, label in levels:
        active_mark = "👉 " if code == current_level else ""
        keyboard.append([InlineKeyboardButton(f"{active_mark}{label}", callback_data=f"set_level:{code}")])
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_level = context.user_data.get("level", "beginner")
    welcome_text = (
        "👋 Chào mừng bạn đến với **Study Bot - Trợ lý học tập**!\n\n"
        "⚡ **Các chức năng chính (Bấm nút bên dưới để chọn nhanh):**\n"
        "• 📖 **Tra từ vựng**: Gõ `/vocab <từ>` (có IPA, loại từ, nghĩa TV, ví dụ song ngữ).\n"
        "• 🌐 **Dịch câu**: Gõ `/translate <câu>` (hoặc `/dich <câu>`) để dịch và phân tích ngữ pháp.\n"
        "• 🎯 **Đổi cấp độ**: Gõ `/level` để chọn cấp độ phù hợp.\n"
        "• 💬 **Hỏi gia sư AI**: Nhắn bất kỳ câu hỏi nào để được giảng giải chi tiết.\n\n"
        f"🎯 Cấp độ hiện tại của bạn: **{current_level.capitalize()}**"
    )
    await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Nếu người dùng truyền trực tiếp: /level intermediate
    if context.args and context.args[0].lower() in settings.VALID_LEVELS:
        new_level = context.args[0].lower()
        context.user_data["level"] = new_level
        await update.message.reply_text(
            f"✅ Đã đổi cấp độ học tập thành: **{new_level.capitalize()}**!",
            reply_markup=MAIN_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # Nếu không truyền tham số: Hiển thị bảng nút bấm Inline để bấm chọn
    current_level = context.user_data.get("level", "beginner")
    msg = (
        "🎯 **Chọn cấp độ học tập của bạn:**\n\n"
        "• **Cơ bản (Beginner)**: Giải thích ngắn gọn, dễ hiểu, nhiều ví dụ đời sống.\n"
        "• **Trung cấp (Intermediate)**: Mạch lạc, nêu rõ công thức & bản chất.\n"
        "• **Nâng cao (Advanced)**: Đi sâu vào học thuật, tư duy phản biện & bẫy ngữ pháp."
    )
    await update.message.reply_text(
        msg,
        reply_markup=get_level_inline_keyboard(current_level),
        parse_mode="Markdown"
    )

async def level_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data and data.startswith("set_level:"):
        chosen_level = data.split(":", 1)[1]
        context.user_data["level"] = chosen_level
        
        level_map = {
            "beginner": "🟢 Cơ bản (Beginner)",
            "intermediate": "🟡 Trung cấp (Intermediate)",
            "advanced": "🔴 Nâng cao (Advanced)"
        }
        level_name = level_map.get(chosen_level, chosen_level.capitalize())
        
        await query.edit_message_text(
            f"✅ **Đã cập nhật cấp độ học tập thành:**\n{level_name}\n\n"
            f"Các câu hỏi tiếp theo và tra từ vựng sẽ được tinh chỉnh theo cấp độ này!",
            reply_markup=get_level_inline_keyboard(chosen_level),
            parse_mode="Markdown"
        )

async def vocab_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Vui lòng nhập từ bạn muốn tra. Ví dụ:\n"
            "• `/vocab achieve`\n"
            "• `/vocab diligent`\n"
            "• `/vocab resilience`",
            reply_markup=MAIN_KEYBOARD,
            parse_mode="Markdown"
        )
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
    
    await update.message.reply_text(reply, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Vui lòng nhập câu bạn muốn dịch. Ví dụ:\n"
            "• `/translate Practice makes perfect.`\n"
            "• `/dich Học tập là chìa khóa mở ra tương lai.`",
            reply_markup=MAIN_KEYBOARD,
            parse_mode="Markdown"
        )
        return
        
    raw_sentence = " ".join(context.args)
    is_safe, sentence, err_msg = validate_and_sanitize_input(raw_sentence)
    if not is_safe:
        await update.message.reply_text(f"⚠️ {err_msg}")
        return

    chat_id = str(update.effective_chat.id)
    level = context.user_data.get("level", "beginner")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    translate_prompt = (
        f"Hãy dịch câu sau một cách tự nhiên và chính xác nhất (nếu câu là tiếng Anh thì dịch sang tiếng Việt, nếu là tiếng Việt thì dịch sang tiếng Anh):\n"
        f"\"{sentence}\"\n\n"
        f"Hãy trình bày câu trả lời rõ ràng theo cấu trúc sau:\n"
        f"🌐 **Bản dịch:**\n<nội dung bản dịch>\n\n"
        f"📝 **Cấu trúc ngữ pháp:**\n<phân tích thì, thành phần hoặc cấu trúc ngữ pháp dùng trong câu>\n\n"
        f"💡 **Từ vựng & Cụm từ hay:**\n<liệt kê các từ vựng hoặc collocations/idioms trong câu kèm nghĩa>"
    )
    
    messages = [{"role": "user", "content": translate_prompt}]
    response_data = generate_chat_response(messages, level=level)
    answer = response_data.get("answer", "Xin lỗi, không thể dịch câu này lúc này.")

    save_message(f"tg_{chat_id}", "user", f"/translate {sentence}", msg_type="translate")
    save_message(f"tg_{chat_id}", "bot", answer, msg_type="translate")

    await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = str(update.effective_chat.id)
    
    # Xử lý các nút bấm nhanh trên bàn phím
    if text == "📖 Tra từ vựng":
        await update.message.reply_text(
            "📖 **Cách tra từ vựng:**\n"
            "Bạn hãy nhập lệnh `/vocab <từ>`, ví dụ:\n"
            "• `/vocab achieve`\n"
            "• `/vocab diligent`\n"
            "• `/vocab persistence`",
            reply_markup=MAIN_KEYBOARD,
            parse_mode="Markdown"
        )
        return
    elif text == "🌐 Dịch câu":
        await update.message.reply_text(
            "🌐 **Cách dịch nguyên câu:**\n"
            "Bạn có thể dùng lệnh `/translate <câu>` hoặc `/dich <câu>`:\n"
            "• `/translate Where there is a will, there is a way.`\n"
            "• Hoặc nhắn trực tiếp: *\"Dịch câu này sang tiếng Anh: Chúc bạn một ngày tốt lành!\"*",
            reply_markup=MAIN_KEYBOARD,
            parse_mode="Markdown"
        )
        return
    elif text == "🎯 Đổi cấp độ":
        await level_command(update, context)
        return
    elif text == "❓ Hướng dẫn":
        await start_command(update, context)
        return

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
    
    await update.message.reply_text(answer, reply_markup=MAIN_KEYBOARD)

async def post_init(application):
    """Cấu hình menu lệnh nhanh của Telegram (Nút Menu ở góc trái)"""
    try:
        commands = [
            BotCommand("vocab", "📖 Tra từ vựng tiếng Anh kèm nghĩa TV"),
            BotCommand("translate", "🌐 Dịch nguyên câu & phân tích ngữ pháp"),
            BotCommand("level", "🎯 Đổi cấp độ học tập"),
            BotCommand("help", "❓ Hướng dẫn sử dụng Study Bot")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Đã thiết lập Telegram Bot Menu Commands thành công.")
    except Exception as e:
        logger.warning(f"Không thể thiết lập Bot commands: {e}")

def run_telegram_bot():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("Chưa cấu hình TELEGRAM_BOT_TOKEN trong .env. Telegram bot sẽ không khởi chạy.")
        return
        
    logging.basicConfig(level=logging.INFO)
    logger.info("Khởi động Telegram Bot...")
    app = ApplicationBuilder().token(token).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("vocab", vocab_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("dich", translate_command))
    app.add_handler(CommandHandler("level", level_command))
    app.add_handler(CallbackQueryHandler(level_callback_handler, pattern=r"^set_level:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == "__main__":
    run_telegram_bot()

