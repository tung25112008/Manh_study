import logging
import asyncio
from telegram import (
    Update,
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
from app.database import save_message, get_db_connection

logger = logging.getLogger(__name__)

def get_stats_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        vocab_count = cursor.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
        msg_count = cursor.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        conn.close()
        return vocab_count, msg_count
    except Exception:
        return 0, 0

def get_main_inline_menu(user_level: str = "beginner") -> InlineKeyboardMarkup:
    level_map = {
        "beginner": "Cơ bản",
        "intermediate": "Trung cấp",
        "advanced": "Nâng cao"
    }
    level_name = level_map.get(user_level, "Cơ bản")
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 Bắt đầu", callback_data="menu_start"),
            InlineKeyboardButton("🔎 Tra cứu", callback_data="menu_vocab")
        ],
        [
            InlineKeyboardButton("🌐 Dịch câu", callback_data="menu_translate"),
            InlineKeyboardButton("💡 Hỏi gia sư AI", callback_data="menu_ask")
        ],
        [
            InlineKeyboardButton(f"🎯 Cấp độ: {level_name}", callback_data="menu_level"),
            InlineKeyboardButton("📊 Thống kê", callback_data="menu_stats")
        ],
        [
            InlineKeyboardButton("📘 Trợ giúp", callback_data="menu_help"),
            InlineKeyboardButton("🔄 Làm mới Menu", callback_data="menu_refresh")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")]
    ])

def get_level_picker_markup(current_level: str = "beginner") -> InlineKeyboardMarkup:
    levels = [
        ("beginner", "🟢 Cơ bản (Beginner)"),
        ("intermediate", "🟡 Trung cấp (Intermediate)"),
        ("advanced", "🔴 Nâng cao (Advanced)")
    ]
    keyboard = []
    for code, label in levels:
        active_mark = "👉 " if code == current_level else ""
        keyboard.append([InlineKeyboardButton(f"{active_mark}{label}", callback_data=f"set_level:{code}")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def get_welcome_text(user_level: str = "beginner") -> str:
    level_map = {
        "beginner": "Cơ bản",
        "intermediate": "Trung cấp",
        "advanced": "Nâng cao"
    }
    level_name = level_map.get(user_level, "Cơ bản")
    return (
        "👋 Chào mừng bạn đến với **Study Bot - Trợ lý học tập**!\n\n"
        "⚡ **Bấm vào các nút bên dưới để chọn chức năng nhanh:**\n"
        "• 🔎 **Tra cứu**: Tra từ vựng tiếng Anh (IPA, nghĩa tiếng Việt, ví dụ song ngữ).\n"
        "• 🌐 **Dịch câu**: Dịch nguyên câu và phân tích ngữ pháp.\n"
        "• 💡 **Hỏi gia sư AI**: Giải bài tập và câu hỏi mọi môn học.\n"
        f"• 🎯 Cấp độ hiện tại của bạn: **{level_name}**"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_level = context.user_data.get("level", "beginner")
    await update.message.reply_text(
        get_welcome_text(current_level),
        reply_markup=get_main_inline_menu(current_level),
        parse_mode="Markdown"
    )

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_level = context.user_data.get("level", "beginner")
    if context.args and context.args[0].lower() in settings.VALID_LEVELS:
        new_level = context.args[0].lower()
        context.user_data["level"] = new_level
        await update.message.reply_text(
            f"✅ Đã đổi cấp độ học tập thành: **{new_level.capitalize()}**!",
            reply_markup=get_main_inline_menu(new_level),
            parse_mode="Markdown"
        )
        return

    msg = (
        "🎯 **Chọn cấp độ học tập của bạn:**\n\n"
        "• **Cơ bản (Beginner)**: Giải thích dễ hiểu, nhiều ví dụ đời sống sinh động.\n"
        "• **Trung cấp (Intermediate)**: Mạch lạc, nêu rõ bản chất và công thức.\n"
        "• **Nâng cao (Advanced)**: Tư duy phản biện, học thuật chuyên sâu và bẫy ngữ pháp."
    )
    await update.message.reply_text(
        msg,
        reply_markup=get_level_picker_markup(current_level),
        parse_mode="Markdown"
    )

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    current_level = context.user_data.get("level", "beginner")

    if data in ("menu_main", "menu_start", "menu_refresh"):
        await query.edit_message_text(
            get_welcome_text(current_level),
            reply_markup=get_main_inline_menu(current_level),
            parse_mode="Markdown"
        )
    elif data == "menu_vocab":
        text = (
            "🔎 **Tra cứu từ vựng tiếng Anh:**\n\n"
            "Bot hỗ trợ phân tích từ vựng có đầy đủ:\n"
            "• Phiên âm quốc tế IPA\n"
            "• Từ loại (Danh từ, Động từ, Tính từ...)\n"
            "• Dịch nghĩa tiếng Việt chuẩn xác\n"
            "• Ví dụ song ngữ minh họa\n"
            "• Từ đồng nghĩa & Trái nghĩa\n\n"
            "👉 **Cách dùng:** Gõ lệnh `/vocab <từ vựng>`\n"
            "Ví dụ:\n"
            "• `/vocab achieve`\n"
            "• `/vocab diligent`\n"
            "• `/vocab resilience`"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_translate":
        text = (
            "🌐 **Dịch nguyên câu tiếng Anh ↔ Tiếng Việt:**\n\n"
            "Bot dịch câu tự nhiên, kèm bóc tách cấu trúc ngữ pháp và từ vựng hay trong câu.\n\n"
            "👉 **Cách dùng:** Gõ lệnh `/translate <câu>` hoặc `/dich <câu>`\n"
            "Ví dụ:\n"
            "• `/translate Practice makes perfect.`\n"
            "• `/dich Học tập là chìa khóa mở ra tương lai.`\n\n"
            "💡 *Mẹo: Bạn cũng có thể nhắn thẳng câu cần dịch vào khung chat!*"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_ask":
        text = (
            "💡 **Hỏi gia sư học tập AI:**\n\n"
            "Bạn có thể hỏi mọi câu hỏi học tập thuộc các môn:\n"
            "• Ngữ pháp & viết luận tiếng Anh\n"
            "• Toán học, Vật lý, Hóa học\n"
            "• Lập trình & Khoa học máy tính\n\n"
            "👉 **Cách dùng:** Chỉ cần gõ trực tiếp câu hỏi của bạn gửi vào khung chat, AI sẽ trả lời chi tiết từng bước!"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_level":
        msg = (
            "🎯 **Chọn cấp độ học tập phù hợp:**\n\n"
            "Bot sẽ tự động điều chỉnh độ khó và phong cách giải thích phù hợp với trình độ của bạn:"
        )
        await query.edit_message_text(
            msg,
            reply_markup=get_level_picker_markup(current_level),
            parse_mode="Markdown"
        )
    elif data and data.startswith("set_level:"):
        chosen_level = data.split(":", 1)[1]
        context.user_data["level"] = chosen_level
        level_map = {
            "beginner": "🟢 Cơ bản (Beginner)",
            "intermediate": "🟡 Trung cấp (Intermediate)",
            "advanced": "🔴 Nâng cao (Advanced)"
        }
        name = level_map.get(chosen_level, chosen_level.capitalize())
        await query.edit_message_text(
            f"✅ **Đã cập nhật cấp độ học tập thành:**\n{name}\n\n"
            f"Mọi câu trả lời tiếp theo sẽ được tối ưu theo trình độ này!",
            reply_markup=get_level_picker_markup(chosen_level),
            parse_mode="Markdown"
        )
    elif data == "menu_stats":
        vocab_count, msg_count = get_stats_data()
        level_map = {
            "beginner": "Cơ bản",
            "intermediate": "Trung cấp",
            "advanced": "Nâng cao"
        }
        level_name = level_map.get(current_level, "Cơ bản")
        text = (
            "📊 **Thống kê hoạt động của Study Bot:**\n\n"
            f"• 🎯 Cấp độ người học: **{level_name}**\n"
            f"• 📚 Số từ vựng đã lưu trong cache: **{vocab_count} từ**\n"
            f"• 💬 Tổng số lượt tin nhắn học tập: **{msg_count} lượt**\n"
            f"• ⚡ Động cơ AI: **Google Gemini / FastAPI**\n"
            f"• 🟢 Trạng thái hệ thống: **Hoạt động ổn định 24/7**"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_help":
        text = (
            "📘 **Hướng dẫn sử dụng Study Bot:**\n\n"
            "1. `/vocab <từ>`: Tra từ vựng có phiên âm IPA, nghĩa tiếng Việt, ví dụ song ngữ.\n"
            "2. `/translate <câu>`: Dịch câu song ngữ kèm phân tích cấu trúc ngữ pháp.\n"
            "3. `/level`: Bật bảng chọn cấp độ học tập.\n"
            "4. `/help`: Xem lại hướng dẫn này.\n"
            "5. **Hỏi bài**: Nhắn trực tiếp câu hỏi bất kỳ vào chat để được gia sư AI giải thích."
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")

async def vocab_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Vui lòng nhập từ bạn muốn tra. Ví dụ:\n"
            "• `/vocab achieve`\n"
            "• `/vocab diligent`\n"
            "• `/vocab resilience`",
            reply_markup=get_main_inline_menu(context.user_data.get("level", "beginner")),
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
    
    await update.message.reply_text(
        reply,
        reply_markup=get_main_inline_menu(level),
        parse_mode="Markdown"
    )

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Vui lòng nhập câu bạn muốn dịch. Ví dụ:\n"
            "• `/translate Practice makes perfect.`\n"
            "• `/dich Học tập là chìa khóa mở ra tương lai.`",
            reply_markup=get_main_inline_menu(context.user_data.get("level", "beginner")),
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

    await update.message.reply_text(
        answer,
        reply_markup=get_main_inline_menu(level),
        parse_mode="Markdown"
    )

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
    
    await update.message.reply_text(
        answer,
        reply_markup=get_main_inline_menu(level)
    )

async def post_init(application):
    """Cấu hình menu lệnh nhanh của Telegram (Nút Menu ở góc trái)"""
    try:
        commands = [
            BotCommand("start", "🚀 Bật Menu phím bấm tương tác"),
            BotCommand("vocab", "🔎 Tra từ vựng tiếng Anh (nghĩa TV, IPA, ví dụ)"),
            BotCommand("translate", "🌐 Dịch nguyên câu & phân tích ngữ pháp"),
            BotCommand("level", "🎯 Đổi cấp độ học tập"),
            BotCommand("help", "📘 Hướng dẫn sử dụng Study Bot")
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
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("vocab", vocab_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("dich", translate_command))
    app.add_handler(CommandHandler("level", level_command))
    app.add_handler(CallbackQueryHandler(menu_callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == "__main__":
    run_telegram_bot()


