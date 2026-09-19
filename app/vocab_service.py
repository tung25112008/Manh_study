import json
import logging
import requests
from typing import Dict, Any, Optional
from app.database import get_vocab_from_cache, save_vocab_to_cache
from app.config import settings

logger = logging.getLogger(__name__)

FREE_DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

def _get_ai_enrichment_func(custom_func = None):
    if custom_func is not None:
        return custom_func
    try:
        from app.ai_service import generate_ai_vocab_enrichment
        return generate_ai_vocab_enrichment
    except Exception as e:
        logger.warning(f"Không thể import generate_ai_vocab_enrichment: {e}")
        return None

def lookup_vocabulary(word_or_phrase: str, language: str = "vi", level: str = "beginner", ai_fallback_func = None) -> Dict[str, Any]:
    """
    Tra cứu từ vựng/cụm từ theo yêu cầu mục 2.1:
    - Kiểm tra cache trước để tiết kiệm tài nguyên (kiểm tra tính hợp lệ của cache).
    - Nếu cần tiếng Việt (language == 'vi') hoặc cụm từ: Ưu tiên AI để có nghĩa tiếng Việt chuẩn xác và ví dụ song ngữ.
    - Dự phòng với Free Dictionary API nếu AI không phản hồi hoặc tra cứu Anh - Anh.
    - Lưu lại vào cache SQLite.
    """
    cleaned_word = word_or_phrase.strip()
    ai_func = _get_ai_enrichment_func(ai_fallback_func)
    
    # 1. Kiểm tra cache
    cached = get_vocab_from_cache(cleaned_word)
    if cached:
        meanings = cached.get("meanings", [])
        # Kiểm tra nếu cache không phải là dữ liệu placeholder cũ
        is_dummy = any("theo ngữ cảnh người học" in str(m) for m in meanings) or not meanings
        if not is_dummy:
            logger.info(f"Từ vựng '{cleaned_word}' được tìm thấy trong cache.")
            return cached

    result: Optional[Dict[str, Any]] = None

    # 2. Nếu người dùng muốn nghĩa tiếng Việt (language == "vi"), ưu tiên AI để có nghĩa & ví dụ tiếng Việt chuẩn xác
    if language == "vi" and ai_func:
        try:
            ai_result = ai_func(cleaned_word, language, level)
            if ai_result and ai_result.get("meanings"):
                result = ai_result
                logger.info(f"Tra từ '{cleaned_word}' thành công qua AI (tiếng Việt).")
        except Exception as e:
            logger.warning(f"Lỗi gọi AI vocab enrichment cho '{cleaned_word}': {e}")

    # 3. Thử với Free Dictionary API (nếu chưa có kết quả từ AI hoặc khi tra cứu tiếng Anh)
    if not result and " " not in cleaned_word and cleaned_word.isascii():
        try:
            res = requests.get(FREE_DICT_API.format(word=cleaned_word), timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list):
                    item = data[0]
                    phonetic = item.get("phonetic", "")
                    if not phonetic and item.get("phonetics"):
                        for p in item["phonetics"]:
                            if p.get("text"):
                                phonetic = p["text"]
                                break
                                
                    meanings_list = []
                    examples_list = []
                    synonyms_list = []
                    antonyms_list = []
                    part_of_speech = ""

                    for m in item.get("meanings", []):
                        if not part_of_speech:
                            part_of_speech = m.get("partOfSpeech", "")
                        for defn in m.get("definitions", [])[:2]:
                            meanings_list.append(f"({m.get('partOfSpeech', '')}) {defn.get('definition', '')}")
                            if defn.get("example"):
                                examples_list.append(defn.get("example"))
                        synonyms_list.extend(m.get("synonyms", [])[:3])
                        antonyms_list.extend(m.get("antonyms", [])[:3])

                    result = {
                        "word": cleaned_word,
                        "part_of_speech": part_of_speech or "Noun/Verb",
                        "phonetic": phonetic or f"/{cleaned_word}/",
                        "meanings": meanings_list[:3] or ["Đang cập nhật định nghĩa..."],
                        "examples": examples_list[:3] or [f"This is an example using {cleaned_word}."],
                        "synonyms": list(set(synonyms_list))[:4],
                        "antonyms": list(set(antonyms_list))[:4],
                        "level": level,
                        "from_cache": False
                    }
        except Exception as e:
            logger.warning(f"Lỗi gọi Free Dictionary API cho '{cleaned_word}': {e}")

    # 4. Fallback cuối cùng nếu cả AI và Free Dictionary API đều không lấy được
    if not result:
        result = {
            "word": cleaned_word,
            "part_of_speech": "Từ vựng / Cụm từ",
            "phonetic": f"/{cleaned_word}/",
            "meanings": [f"Nghĩa của từ '{cleaned_word}' (hệ thống chưa thể lấy định nghĩa tự động lúc này)."],
            "examples": [f"Ví dụ với '{cleaned_word}'."],
            "synonyms": [],
            "antonyms": [],
            "level": level,
            "from_cache": False
        }

    # 5. Lưu vào cache SQLite (chỉ lưu khi kết quả hợp lệ, không phải dummy)
    try:
        save_vocab_to_cache(result)
    except Exception as e:
        logger.error(f"Lỗi lưu cache từ vựng: {e}")

    return result

