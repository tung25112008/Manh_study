import uuid
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.database import (
    init_db,
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    save_message,
    get_messages,
    save_feedback
)
from app.security import check_rate_limit, validate_and_sanitize_input
from app.ai_service import generate_chat_response, generate_ai_vocab_enrichment
from app.vocab_service import lookup_vocabulary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("study_bot")

app = FastAPI(
    title="Study Bot API",
    description="API hệ thống trợ lý học tập và tra cứu từ vựng",
    version="1.0.0"
)

# Bật CORS cho phép gọi API an toàn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đảm bảo database được khởi tạo sẵn sàng
init_db()

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Study Bot Server is running on port %s", settings.PORT)

# --- Pydantic Data Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="Nội dung câu hỏi học tập")
    language: Optional[str] = Field("vi", description="Ngôn ngữ ('vi' hoặc 'en')")
    level: Optional[str] = Field("beginner", description="Cấp độ: beginner, intermediate, advanced")
    conversationId: Optional[str] = Field(None, description="Mã phiên hội thoại (tuỳ chọn)")

class VocabRequest(BaseModel):
    word: str = Field(..., description="Từ hoặc cụm từ cần tra cứu")
    language: Optional[str] = Field("vi", description="Ngôn ngữ giải thích")
    level: Optional[str] = Field("beginner", description="Cấp độ người học")

class FeedbackRequest(BaseModel):
    messageId: int = Field(..., description="ID tin nhắn được đánh giá")
    isHelpful: bool = Field(..., description="Hữu ích hay không")
    comment: Optional[str] = Field("", description="Ý kiến đóng góp")

# --- API Endpoints ---

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    """Endpoint xử lý câu hỏi học tập và duy trì ngữ cảnh (Mục 5.1)."""
    client_ip = request.client.host if request.client else "unknown"
    
    # 1. Rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Bạn đang gửi câu hỏi quá nhanh. Vui lòng đợi ít giây rồi thử lại."
        )

    # 2. Kiểm tra an toàn đầu vào
    is_safe, cleaned_msg, error_msg = validate_and_sanitize_input(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)

    level = req.level.lower() if req.level and req.level.lower() in settings.VALID_LEVELS else "beginner"
    language = req.language or "vi"
    conv_id = req.conversationId

    # 3. Quản lý phiên trò chuyện
    if not conv_id or not get_conversation(conv_id):
        conv_id = str(uuid.uuid4())
        # Tạo tiêu đề tóm tắt từ câu hỏi đầu tiên (tối đa 40 ký tự)
        title = (cleaned_msg[:40] + "...") if len(cleaned_msg) > 40 else cleaned_msg
        create_conversation(conv_id, title=title, level=level, language=language)

    # Lưu câu hỏi của người dùng
    save_message(conv_id, sender="user", content=cleaned_msg, msg_type="chat")

    # 4. Lấy lịch sử hội thoại để duy trì ngữ cảnh
    past_messages = get_messages(conv_id, limit=10)
    ai_history = []
    for m in past_messages:
        role = "user" if m["sender"] == "user" else "model"
        ai_history.append({"role": role, "content": m["content"]})

    # 5. Gọi AI sinh câu trả lời
    try:
        response_data = generate_chat_response(ai_history, level=level, language=language)
    except Exception as e:
        logger.error(f"Lỗi khi tạo phản hồi AI: {e}")
        raise HTTPException(status_code=500, detail="Có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau.")

    answer_text = response_data.get("answer", "")
    tokens_used = response_data.get("usage", {}).get("outputTokens", 0)

    # Lưu câu trả lời của bot
    msg_id = save_message(conv_id, sender="bot", content=answer_text, msg_type="chat", tokens=tokens_used)

    return {
        "messageId": msg_id,
        "answer": answer_text,
        "type": "learning_answer",
        "conversationId": conv_id,
        "level": level,
        "usage": response_data.get("usage", {"inputTokens": 0, "outputTokens": 0})
    }

@app.post("/api/vocab")
async def vocab_endpoint(req: VocabRequest, request: Request):
    """Endpoint tra cứu từ vựng có cấu trúc (Mục 2.1)."""
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Thao tác quá nhanh. Vui lòng thử lại sau ít giây.")

    is_safe, cleaned_word, error_msg = validate_and_sanitize_input(req.word)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)

    level = req.level.lower() if req.level and req.level.lower() in settings.VALID_LEVELS else "beginner"
    
    result = lookup_vocabulary(
        cleaned_word,
        language=req.language or "vi",
        level=level,
        ai_fallback_func=generate_ai_vocab_enrichment
    )
    return result

@app.get("/api/conversations")
async def list_conversations_endpoint():
    """Lấy danh sách các phiên trò chuyện gần đây."""
    return list_conversations(limit=30)

@app.get("/api/conversations/{conv_id}")
async def get_conversation_endpoint(conv_id: str):
    """Lấy nội dung chi tiết của một phiên trò chuyện."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên trò chuyện.")
    messages = get_messages(conv_id, limit=50)
    return {"conversation": conv, "messages": messages}

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    """Xóa một phiên trò chuyện."""
    delete_conversation(conv_id)
    return {"success": True, "message": "Đã xóa phiên trò chuyện thành công."}

@app.post("/api/feedback")
async def feedback_endpoint(req: FeedbackRequest):
    """Ghi nhận đánh giá câu trả lời (Mục 8)."""
    feedback_id = save_feedback(req.messageId, req.isHelpful, req.comment or "")
    return {"success": True, "feedbackId": feedback_id}

@app.get("/api/health")
async def health_check():
    """Endpoint kiểm tra sức khỏe của dịch vụ khi treo VPS."""
    return {
        "status": "healthy",
        "provider": settings.AI_PROVIDER,
        "port": settings.PORT
    }

# Phục vụ giao diện Web tĩnh
static_dir = settings.BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(static_dir / "index.html")
