import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.config import settings
from app.database import log_api_usage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """Bạn là "Study Bot" - một trợ lý gia sư học tập thông minh, sư phạm và chuẩn mực.
Nhiệm vụ của bạn là hỗ trợ học sinh, sinh viên và người tự học nắm vững kiến thức một cách khoa học.

QUY TẮC CỐT LÕI (Mục 2.2 & 5.2):
1. CẤP ĐỘ NGƯỜI HỌC: Hiện tại người học đang ở cấp độ: [{level_upper}].
   - "BEGINNER" (Cơ bản): Dùng từ ngữ gần gũi, giải thích từng bước cực kỳ dễ hiểu, chia nhỏ khái niệm, dùng ví dụ đời sống sinh động.
   - "INTERMEDIATE" (Trung cấp): Giải thích mạch lạc, có cấu trúc chặt chẽ, nêu rõ bản chất và công thức/quy tắc.
   - "ADVANCED" (Nâng cao): Đi sâu vào tư duy phản biện, tối ưu hóa, các trường hợp đặc biệt, liên hệ thực tiễn và học thuật.
2. NGUYÊN TẮC SƯ PHẠM:
   - KHÔNG làm hộ bài tập hoặc viết sẵn bài thi để chép. Thay vào đó, hãy giải thích phương pháp, các bước thực hiện và gợi ý để người học tự làm.
   - Khi thiếu dữ kiện trong câu hỏi, hãy lịch sự hỏi lại để người học bổ sung.
   - Tránh bịa đặt; nếu không chắc chắn về một sự kiện hay số liệu, hãy nói rõ.
3. CẤU TRÚC PHẢN HỒI (Hỗ trợ Markdown và KaTeX cho Toán học):
   - 🎯 **Tóm tắt / Đáp án trọng tâm**
   - 📝 **Giải thích chi tiết từng bước**
   - 💡 **Ví dụ minh họa thực tế**
   - 🚀 **Câu hỏi / Bài tập tương tự để luyện tập**
4. NGÔN NGỮ: Mặc định trả lời bằng {language_label}. Nếu người dùng hỏi bằng tiếng Anh hoặc yêu cầu song ngữ, hãy đáp ứng phù hợp.
"""

def get_system_prompt(level: str = "beginner", language: str = "vi") -> str:
    lang_map = {"vi": "Tiếng Việt", "en": "Tiếng Anh"}
    return SYSTEM_PROMPT_TEMPLATE.format(
        level_upper=level.upper(),
        language_label=lang_map.get(language, "Tiếng Việt")
    )

def generate_chat_response(messages: List[Dict[str, str]], level: str = "beginner", language: str = "vi") -> Dict[str, Any]:
    """
    Tạo phản hồi học tập từ AI theo ngữ cảnh hội thoại nhiều lượt.
    """
    provider = settings.AI_PROVIDER.lower()
    system_prompt = get_system_prompt(level, language)
    
    # 1. Thử gọi Google Gemini nếu có key hoặc được cấu hình
    if provider == "gemini" and settings.GEMINI_API_KEY:
        try:
            return _call_gemini(messages, system_prompt, level)
        except Exception as e:
            logger.error(f"Lỗi gọi Gemini API: {e}")
            # Fallback sang Mock nếu lỗi
            
    # 2. Thử gọi OpenAI nếu có key
    if provider == "openai" and settings.OPENAI_API_KEY:
        try:
            return _call_openai(messages, system_prompt, level)
        except Exception as e:
            logger.error(f"Lỗi gọi OpenAI API: {e}")

    # 3. Chế độ Mock / Demo (hoạt động ngay khi chưa cấu hình API Key)
    return _generate_mock_response(messages, level, language)

def _call_gemini(messages: List[Dict[str, str]], system_prompt: str, level: str) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Chuyển đổi lịch sử hội thoại
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=msg["content"])]
        ))
        
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        max_output_tokens=1000,
    )
    
    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )
    
    # Trích xuất số token
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        
    log_api_usage("gemini", model_name, input_tokens, output_tokens, "/api/chat")
    
    return {
        "answer": response.text,
        "type": "learning_answer",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "provider": "gemini"
        }
    }

def _call_openai(messages: List[Dict[str, str]], system_prompt: str, level: str) -> Dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    payload_msgs = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        payload_msgs.append({"role": msg["role"], "content": msg["content"]})
        
    model_name = settings.OPENAI_MODEL or "gpt-4o-mini"
    response = client.chat.completions.create(
        model=model_name,
        messages=payload_msgs,
        temperature=0.7,
        max_tokens=1000
    )
    
    choice = response.choices[0]
    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0
    
    log_api_usage("openai", model_name, input_tokens, output_tokens, "/api/chat")
    
    return {
        "answer": choice.message.content,
        "type": "learning_answer",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "provider": "openai"
        }
    }

def _generate_mock_response(messages: List[Dict[str, str]], level: str, language: str) -> Dict[str, Any]:
    """Phản hồi thông minh giả lập khi chưa nhập API Key để người dùng thử nghiệm."""
    last_msg = messages[-1]["content"] if messages else ""
    
    demo_answer = (
        f"🎯 **Tóm tắt câu trả lời (Cấp độ: {level.capitalize()})**\n\n"
        f"Chào bạn! Tôi đã nhận được câu hỏi: *\"{last_msg}\"*.\n\n"
        f"📝 **Giải thích phương pháp:**\n"
        f"1. Xác định khái niệm chính trong câu hỏi học tập của bạn.\n"
        f"2. Áp dụng quy tắc hoặc lý thuyết nền tảng tương ứng.\n"
        f"3. Chia nhỏ các bước suy luận để nắm bản chất thay vì học vẹt.\n\n"
        f"💡 **Ví dụ minh họa:**\n"
        f"Nếu đây là câu hỏi về toán học hoặc ngữ pháp, hãy liên hệ với các mẫu bài toán/câu tương tự trong sách giáo khoa.\n\n"
        f"🚀 **Gợi ý tự luyện:**\n"
        f"Thử giải lại một bài tương tự với số liệu hoặc từ vựng mới.\n\n"
        f"> 💡 *Mẹo: Hãy thêm `GEMINI_API_KEY` vào file `.env` để kích hoạt toàn bộ sức mạnh của AI thông minh!*"
    )
    
    return {
        "answer": demo_answer,
        "type": "learning_answer",
        "usage": {
            "inputTokens": 50,
            "outputTokens": 150,
            "provider": "mock_demo"
        }
    }

def generate_ai_vocab_enrichment(word: str, language: str = "vi", level: str = "beginner") -> Optional[Dict[str, Any]]:
    """Dùng AI để bóc tách từ vựng thành JSON chuẩn xác nếu từ điển không có."""
    prompt = f"""Hãy phân tích từ vựng hoặc cụm từ "{word}" cho người học trình độ {level}.
Trả về định dạng JSON thuần túy (không dùng markdown block, chỉ JSON hợp lệ) có các trường:
{{
  "word": "{word}",
  "part_of_speech": "Từ loại (Noun/Verb/Adj...)",
  "phonetic": "/phiên âm IPA/",
  "meanings": ["Nghĩa 1 kèm giải thích ngắn bằng tiếng Việt", "Nghĩa 2..."],
  "examples": ["Ví dụ 1 bằng tiếng Anh kèm dịch nghĩa tiếng Việt", "Ví dụ 2..."],
  "synonyms": ["Từ đồng nghĩa 1", "Từ đồng nghĩa 2"],
  "antonyms": ["Từ trái nghĩa 1", "Từ trái nghĩa 2"],
  "level": "{level}"
}}"""

    messages = [{"role": "user", "content": prompt}]
    try:
        if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            res = _call_gemini(messages, "Bạn là từ điển ngôn ngữ. Chỉ xuất kết quả dưới dạng JSON hợp lệ.", level)
            raw = res.get("answer", "")
            # Trích xuất JSON
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                data["from_cache"] = False
                return data
        elif settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            res = _call_openai(messages, "Bạn là từ điển ngôn ngữ. Chỉ xuất kết quả dưới dạng JSON hợp lệ.", level)
            raw = res.get("answer", "")
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                data["from_cache"] = False
                return data
    except Exception as e:
        logger.warning(f"Lỗi AI vocab enrichment: {e}")
        
    return None
