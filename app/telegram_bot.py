import logging
import asyncio
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ForceReply,
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

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Tạo bàn phím nút bấm cố định ở thanh dưới cùng theo đúng mẫu 9 nút (5 hàng)"""
    keyboard = [
        [
            KeyboardButton("🚀 Bắt đầu"),
            KeyboardButton("💳 Nạp điểm")
        ],
        [
            KeyboardButton("🔎 Tra cứu"),
            KeyboardButton("📡 Trạng thái")
        ],
        [
            KeyboardButton("🔗 Mời bạn bè"),
            KeyboardButton("🔌 API")
        ],
        [
            KeyboardButton("📘 Trợ giúp"),
            KeyboardButton("💬 Hỗ trợ")
        ],
        [
            KeyboardButton("🌐 Ngôn ngữ")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_main_inline_menu(user_level: str = "beginner") -> InlineKeyboardMarkup:
    """Tạo inline keyboard đính kèm tin nhắn theo mẫu 9 nút"""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Bắt đầu", callback_data="menu_start"),
            InlineKeyboardButton("💳 Nạp điểm", callback_data="menu_points")
        ],
        [
            InlineKeyboardButton("🔎 Tra cứu", callback_data="menu_vocab"),
            InlineKeyboardButton("📡 Trạng thái", callback_data="menu_status")
        ],
        [
            InlineKeyboardButton("🔗 Mời bạn bè", callback_data="menu_invite"),
            InlineKeyboardButton("🔌 API", callback_data="menu_api")
        ],
        [
            InlineKeyboardButton("📘 Trợ giúp", callback_data="menu_help"),
            InlineKeyboardButton("💬 Hỗ trợ", callback_data="menu_support")
        ],
        [
            InlineKeyboardButton("🌐 Ngôn ngữ", callback_data="menu_lang")
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
        reply_markup=get_main_reply_keyboard(),
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
        context.user_data["awaiting"] = "vocab"
        text = (
            "🔎 **Tra cứu từ vựng tiếng Anh:**\n\n"
            "👉 Hãy **nhập từ bạn muốn tra** vào thanh chat bên dưới rồi gửi cho bot.\n\n"
            "*(Hoặc bấm vào lệnh /vocab rồi nhập từ, ví dụ: `/vocab achieve`)*"
        )
        await query.message.reply_text(
            text,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Nhập từ vựng cần tra (vd: achieve)..."),
            parse_mode="Markdown"
        )
    elif data == "menu_translate":
        context.user_data["awaiting"] = "translate"
        text = (
            "🌐 **Dịch nguyên câu tiếng Anh ↔ Tiếng Việt:**\n\n"
            "👉 Hãy **nhập câu bạn muốn dịch** vào thanh chat bên dưới rồi gửi cho bot.\n\n"
            "*(Hoặc bấm vào lệnh /translate rồi nhập câu)*"
        )
        await query.message.reply_text(
            text,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Nhập câu bạn muốn dịch..."),
            parse_mode="Markdown"
        )
    elif data == "menu_ask":
        context.user_data["awaiting"] = "ask"
        text = (
            "💡 **Hỏi gia sư học tập AI:**\n\n"
            "👉 Hãy **nhập câu hỏi học tập** của bạn vào thanh chat bên dưới rồi gửi cho bot:"
        )
        await query.message.reply_text(
            text,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Nhập câu hỏi học tập của bạn..."),
            parse_mode="Markdown"
        )
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
    elif data == "menu_points":
        text = (
            "💳 **Thông tin điểm & Tài khoản:**\n\n"
            "• 👤 Học viên: **Thành viên Study Bot**\n"
            "• 💎 Điểm học tập: **1,000 / 1,000 điểm** (Đầy đủ)\n"
            "• 🎁 Gói dịch vụ: **Miễn phí không giới hạn (Free Pro)**\n"
            "• ⚡ Tra từ vựng & Hỏi bài: **Không giới hạn lượt dùng**\n\n"
            "💡 *Mỗi lần tra từ vựng hoặc hỏi bài với bot, bạn đều được tích lũy điểm chuyên cần!*"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_status":
        vocab_count, msg_count = get_stats_data()
        level_map = {
            "beginner": "Cơ bản",
            "intermediate": "Trung cấp",
            "advanced": "Nâng cao"
        }
        level_name = level_map.get(current_level, "Cơ bản")
        text = (
            "📡 **Trạng thái hệ thống (System Status):**\n\n"
            "• 🟢 Máy chủ VPS: **Hoạt động ổn định 24/7**\n"
            "• 🧠 Trí tuệ nhân tạo: **Google Gemini 2.5 Flash (Online)**\n"
            f"• 🎯 Cấp độ hiện tại: **{level_name}**\n"
            f"• 📚 Từ vựng trong bộ đệm: **{vocab_count} từ**\n"
            f"• 💬 Lượt học tập đã phục vụ: **{msg_count} tin nhắn**\n"
            "• ⏱ Tốc độ phản hồi: **< 1.2 giây**"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_invite":
        text = (
            "🔗 **Mời bạn bè cùng học tập:**\n\n"
            "Cùng chia sẻ Study Bot để bạn bè cùng tra cứu từ vựng tiếng Anh và hỏi bài tập nhé!\n\n"
            "👉 **Link bot:** https://t.me/manh_141208bot"
        )
        share_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("↗️ Chia sẻ cho bạn bè", url="https://t.me/share/url?url=https://t.me/manh_141208bot&text=H%E1%BB%8Dc%20ti%E1%BA%BFng%20Anh%20v%C3%A0%20gi%E1%BA%A3i%20b%C3%A0i%20t%E1%BA%ADp%20c%E1%BB%B1c%20nhanh%20v%E1%BB%9Bi%20Study%20Bot!")],
            [InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")]
        ])
        await query.edit_message_text(text, reply_markup=share_keyboard, parse_mode="Markdown")
    elif data == "menu_api":
        text = (
            "🔌 **Cổng kết nối API & Máy chủ VPS:**\n\n"
            "Study Bot được xây dựng trên nền tảng FastAPI hiệu năng cao:\n\n"
            "• 🌐 Giao diện Web: `http://localhost:8000`\n"
            "• 📑 Tài liệu Swagger API: `/docs`\n"
            "• 🔍 API Tra từ vựng: `POST /api/vocab`\n"
            "• 💬 API Chat AI: `POST /api/chat`\n"
            "• 🛡 Bảo vệ: Rate-limiting & Input sanitization"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_support":
        text = (
            "💬 **Trung tâm hỗ trợ & Liên hệ:**\n\n"
            "Nếu bạn gặp sự cố kỹ thuật hoặc muốn đóng góp ý kiến nâng cấp bot:\n\n"
            "• 👨‍💻 Quản trị viên: @tung25112008\n"
            "• 🤖 Phiên bản: **Study Bot v1.4.0**\n"
            "• 💌 Hỗ trợ: Bạn chỉ cần nhắn thẳng câu hỏi vào khung chat này!"
        )
        await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode="Markdown")
    elif data == "menu_lang":
        text = (
            "🌐 **Cài đặt ngôn ngữ hiển thị (Language Settings):**\n\n"
            "Vui lòng chọn ngôn ngữ giao diện bot:"
        )
        lang_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇻🇳 Tiếng Việt (Mặc định)", callback_data="set_lang:vi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")],
            [InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")]
        ])
        await query.edit_message_text(text, reply_markup=lang_keyboard, parse_mode="Markdown")
    elif data and data.startswith("set_lang:"):
        lang_code = data.split(":", 1)[1]
        context.user_data["language"] = lang_code
        lang_name = "Tiếng Việt 🇻🇳" if lang_code == "vi" else "English 🇬🇧"
        await query.edit_message_text(
            f"✅ **Đã cập nhật ngôn ngữ:** {lang_name}",
            reply_markup=get_back_button(),
            parse_mode="Markdown"
        )
    elif data == "menu_help":
        text = (
            "📘 **Hướng dẫn sử dụng chi tiết:**\n\n"
            "1. 🔎 **Tra cứu từ vựng**: Bấm `🔎 Tra cứu` hoặc gõ `/vocab <từ>`\n"
            "2. 🌐 **Dịch câu**: Gõ `/translate <câu>` hoặc `/dich <câu>`\n"
            "3. 🎯 **Đổi cấp độ**: Gõ `/level` để chọn Beginner / Intermediate / Advanced\n"
            "4. 💬 **Hỏi bài tập**: Nhắn thẳng câu hỏi vào chat để AI giải thích chi tiết."
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
        reply_markup=get_main_reply_keyboard(),
        parse_mode="Markdown"
    )

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Vui lòng nhập câu bạn muốn dịch. Ví dụ:\n"
            "• `/translate Practice makes perfect.`\n"
            "• `/dich Học tập là chìa khóa mở ra tương lai.`",
            reply_markup=get_main_reply_keyboard(),
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
        reply_markup=get_main_reply_keyboard(),
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

    # 0. Bắt 9 nút bấm từ giao diện ReplyKeyboardMarkup cố định ở thanh dưới
    if cleaned_text in ("🚀 Bắt đầu", "Bắt đầu"):
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            get_welcome_text(level),
            reply_markup=get_main_reply_keyboard(),
            parse_mode="Markdown"
        )
        return

    if cleaned_text in ("💳 Nạp điểm", "Nạp điểm"):
        context.user_data.pop("awaiting", None)
        credit_text = (
            "💳 **Thông tin điểm & Tài khoản:**\n\n"
            "• 👤 Học viên: **Thành viên Study Bot**\n"
            "• 💎 Điểm học tập: **1,000 / 1,000 điểm** (Đầy đủ)\n"
            "• 🎁 Gói dịch vụ: **Miễn phí không giới hạn (Free Pro)**\n"
            "• ⚡ Tra từ vựng & Hỏi bài: **Không giới hạn lượt dùng**\n\n"
            "💡 *Mỗi lần tra từ vựng hoặc hỏi bài với bot, bạn đều được tích lũy điểm chuyên cần!*"
        )
        await update.message.reply_text(credit_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    if cleaned_text in ("🔎 Tra cứu", "Tra cứu"):
        context.user_data["awaiting"] = "vocab"
        text_prompt = (
            "🔎 **Tra cứu từ vựng tiếng Anh:**\n\n"
            "👉 Hãy **nhập từ bạn muốn tra** vào thanh chat bên dưới rồi gửi cho bot nhé.\n\n"
            "*(Ví dụ: nhập `achieve`, `diligent`, `resilience`...)*"
        )
        await update.message.reply_text(
            text_prompt,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Nhập từ vựng cần tra (vd: achieve)..."),
            parse_mode="Markdown"
        )
        return

    if cleaned_text in ("📡 Trạng thái", "Trạng thái"):
        context.user_data.pop("awaiting", None)
        vocab_count, msg_count = get_stats_data()
        level_map = {
            "beginner": "Cơ bản",
            "intermediate": "Trung cấp",
            "advanced": "Nâng cao"
        }
        level_name = level_map.get(level, "Cơ bản")
        status_text = (
            "📡 **Trạng thái hệ thống (System Status):**\n\n"
            "• 🟢 Máy chủ VPS: **Hoạt động ổn định 24/7**\n"
            "• 🧠 Trí tuệ nhân tạo: **Google Gemini 2.5 Flash (Online)**\n"
            f"• 🎯 Cấp độ hiện tại: **{level_name}**\n"
            f"• 📚 Từ vựng trong bộ đệm: **{vocab_count} từ**\n"
            f"• 💬 Lượt học tập đã phục vụ: **{msg_count} tin nhắn**\n"
            "• ⏱ Tốc độ phản hồi: **< 1.2 giây**"
        )
        await update.message.reply_text(status_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    if cleaned_text in ("🔗 Mời bạn bè", "Mời bạn bè"):
        context.user_data.pop("awaiting", None)
        invite_text = (
            "🔗 **Mời bạn bè cùng học tập:**\n\n"
            "Cùng chia sẻ Study Bot để bạn bè cùng tra cứu từ vựng tiếng Anh và hỏi bài tập nhé!\n\n"
            "👉 **Link bot:** https://t.me/manh_141208bot"
        )
        share_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("↗️ Chia sẻ cho bạn bè", url="https://t.me/share/url?url=https://t.me/manh_141208bot&text=H%E1%BB%8Dc%20ti%E1%BA%BFng%20Anh%20v%C3%A0%20gi%E1%BA%A3i%20b%C3%A0i%20t%E1%BA%ADp%20c%E1%BB%B1c%20nhanh%20v%E1%BB%9Bi%20Study%20Bot!")],
            [InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")]
        ])
        await update.message.reply_text(invite_text, reply_markup=share_keyboard, parse_mode="Markdown")
        return

    if cleaned_text in ("🔌 API", "API"):
        context.user_data.pop("awaiting", None)
        api_text = (
            "🔌 **Cổng kết nối API & Máy chủ VPS:**\n\n"
            "Study Bot được xây dựng trên nền tảng FastAPI hiệu năng cao:\n\n"
            "• 🌐 Giao diện Web: `http://localhost:8000`\n"
            "• 📑 Tài liệu Swagger API: `/docs`\n"
            "• 🔍 API Tra từ vựng: `POST /api/vocab`\n"
            "• 💬 API Chat AI: `POST /api/chat`\n"
            "• 🛡 Bảo vệ: Rate-limiting & Input sanitization"
        )
        await update.message.reply_text(api_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    if cleaned_text in ("📘 Trợ giúp", "Trợ giúp"):
        context.user_data.pop("awaiting", None)
        help_text = (
            "📘 **Hướng dẫn sử dụng chi tiết:**\n\n"
            "1. 🔎 **Tra cứu từ vựng**: Bấm `🔎 Tra cứu` hoặc gõ `/vocab <từ>`\n"
            "2. 🌐 **Dịch câu**: Gõ `/translate <câu>` hoặc `/dich <câu>`\n"
            "3. 🎯 **Đổi cấp độ**: Gõ `/level` để chọn Beginner / Intermediate / Advanced\n"
            "4. 💬 **Hỏi bài tập**: Nhắn thẳng câu hỏi vào chat để AI giải thích chi tiết."
        )
        await update.message.reply_text(help_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    if cleaned_text in ("💬 Hỗ trợ", "Hỗ trợ"):
        context.user_data.pop("awaiting", None)
        support_text = (
            "💬 **Trung tâm hỗ trợ & Liên hệ:**\n\n"
            "Nếu bạn gặp sự cố kỹ thuật hoặc muốn đóng góp ý kiến nâng cấp bot:\n\n"
            "• 👨‍💻 Quản trị viên: @tung25112008\n"
            "• 🤖 Phiên bản: **Study Bot v1.4.0**\n"
            "• 💌 Hỗ trợ: Bạn chỉ cần nhắn thẳng câu hỏi vào khung chat này!"
        )
        await update.message.reply_text(support_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    if cleaned_text in ("🌐 Ngôn ngữ", "Ngôn ngữ"):
        context.user_data.pop("awaiting", None)
        lang_text = (
            "🌐 **Cài đặt ngôn ngữ hiển thị (Language Settings):**\n\n"
            "Vui lòng chọn ngôn ngữ giao diện bot:"
        )
        lang_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇻🇳 Tiếng Việt (Mặc định)", callback_data="set_lang:vi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")],
            [InlineKeyboardButton("🔙 Quay lại Menu chính", callback_data="menu_main")]
        ])
        await update.message.reply_text(lang_text, reply_markup=lang_keyboard, parse_mode="Markdown")
        return

    awaiting = context.user_data.pop("awaiting", None)

    # 1. Nếu người dùng vừa bấm nút 'Tra cứu' và nhập từ vựng
    if awaiting == "vocab":
        word_to_lookup = cleaned_text.removeprefix("/vocab").strip() if cleaned_text.startswith("/vocab") else cleaned_text
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        res = lookup_vocabulary(word_to_lookup, language="vi", level=level)
        
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
        save_message(f"tg_{chat_id}", "user", f"/vocab {word_to_lookup}", msg_type="vocab")
        save_message(f"tg_{chat_id}", "bot", reply, msg_type="vocab")
        await update.message.reply_text(reply, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    # 2. Nếu người dùng vừa bấm nút 'Dịch câu' và nhập câu cần dịch
    if awaiting == "translate":
        sentence = cleaned_text.removeprefix("/translate").removeprefix("/dich").strip() if (cleaned_text.startswith("/translate") or cleaned_text.startswith("/dich")) else cleaned_text
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
        await update.message.reply_text(answer, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")
        return

    # 3. Câu hỏi học tập thông thường
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    messages = [{"role": "user", "content": cleaned_text}]
    response_data = generate_chat_response(messages, level=level)
    answer = response_data.get("answer", "Xin lỗi, không nhận được phản hồi.")
    
    # Lưu vào database
    save_message(f"tg_{chat_id}", "user", cleaned_text)
    save_message(f"tg_{chat_id}", "bot", answer)
    
    await update.message.reply_text(
        answer,
        reply_markup=get_main_reply_keyboard()
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


