import time
import re
from typing import Tuple, Optional
from collections import defaultdict
from app.config import settings

# Lưu trữ lịch sử gọi API theo IP để hạn chế spam (Rate Limiting)
_ip_request_history = defaultdict(list)

# Các mẫu phát hiện Prompt Injection nguy hiểm
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+prompts",
    r"system\s*prompt",
    r"you\s+are\s+now\s+in\s+(developer|dan|jailbreak)\s+mode",
    r"reveal\s+(your\s+)?(system|internal)\s+(prompt|instructions)",
    r"repeat\s+the\s+words\s+above",
    r"bỏ\s+qua\s+(toàn\s+bộ\s+)?hướng\s+dẫn\s+trước",
    r"tiết\s+lộ\s+prompt\s+hệ\s+thống",
]

def check_rate_limit(client_ip: str) -> bool:
    """Kiểm tra giới hạn tần suất yêu cầu trên 1 phút."""
    now = time.time()
    window = 60.0  # 60 giây
    
    # Dọn dẹp các mốc thời gian cũ hơn 60s
    requests = [t for t in _ip_request_history[client_ip] if now - t < window]
    
    if len(requests) >= settings.MAX_MESSAGES_PER_MINUTE:
        return False
        
    requests.append(now)
    _ip_request_history[client_ip] = requests
    return True

def validate_and_sanitize_input(text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Kiểm tra tính an toàn của nội dung người dùng nhập vào.
    Trả về: (is_safe, sanitized_text, error_message)
    """
    if not text or not text.strip():
        return False, "", "Nội dung câu hỏi không được để trống."
        
    cleaned = text.strip()
    
    # 1. Kiểm tra độ dài tối đa
    if len(cleaned) > settings.MAX_INPUT_LENGTH:
        return False, "", f"Câu hỏi quá dài (tối đa {settings.MAX_INPUT_LENGTH} ký tự). Hãy rút ngắn câu hỏi."

    # 2. Kiểm tra các chủ đề bị cấm (Mục 2.4 & Mục 5.2)
    cleaned_lower = cleaned.lower()
    for bad_kw in settings.PROHIBITED_TOPICS:
        if bad_kw in cleaned_lower:
            return False, "", "Bot hỗ trợ học tập và tư duy, không hỗ trợ các hành vi gian lận thi cử hay làm hộ bài thi."

    # 3. Kiểm tra Prompt Injection
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False, "", "Phát hiện câu lệnh can thiệp hệ thống không hợp lệ. Vui lòng đặt câu hỏi học tập chuẩn mực."

    return True, cleaned, None
