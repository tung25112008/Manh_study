import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo toàn bộ bảng dữ liệu theo yêu cầu kỹ thuật mục 5.3."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng users (lưu cấu hình người học)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT,
            preferred_level TEXT DEFAULT 'beginner',
            preferred_language TEXT DEFAULT 'vi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Bảng conversations (quản lý phiên học tập)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'guest',
            title TEXT,
            level TEXT DEFAULT 'beginner',
            language TEXT DEFAULT 'vi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Bảng messages (câu hỏi & câu trả lời)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            sender TEXT NOT NULL, -- 'user' hoặc 'bot'
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'chat', -- 'chat' hoặc 'vocab'
            tokens_used INTEGER DEFAULT 0,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
        )
    """)
    
    # 4. Bảng vocabulary (cache kết quả tra cứu từ vựng để tiết kiệm API)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            part_of_speech TEXT,
            phonetic TEXT,
            meanings_json TEXT NOT NULL,
            examples_json TEXT NOT NULL,
            synonyms_json TEXT,
            antonyms_json TEXT,
            level TEXT DEFAULT 'beginner',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 5. Bảng api_usage (thống kê token và chi phí theo dõi)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            endpoint TEXT,
            status TEXT DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 6. Bảng feedback (đánh giá câu trả lời hữu ích / không hữu ích)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            is_helpful BOOLEAN NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", settings.DB_PATH)

# --- Các hàm thao tác cơ sở dữ liệu ---

def create_conversation(conv_id: str, title: str, level: str = "beginner", language: str = "vi", user_id: str = "guest") -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (id, user_id, title, level, language) VALUES (?, ?, ?, ?, ?)",
        (conv_id, user_id, title, level, language)
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "title": title, "level": level, "language": language}

def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def list_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_conversation(conv_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return True

def save_message(conv_id: str, sender: str, content: str, msg_type: str = "chat", tokens: int = 0, metadata: dict = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO messages (conversation_id, sender, content, msg_type, tokens_used, metadata_json) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (conv_id, sender, content, msg_type, tokens, json.dumps(metadata or {}, ensure_ascii=False))
    )
    msg_id = cursor.lastrowid
    # Cập nhật updated_at của conversation
    cursor.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conv_id,)
    )
    conn.commit()
    conn.close()
    return msg_id

def get_messages(conv_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
        (conv_id, limit)
    )
    results = []
    for r in rows:
        d = dict(r)
        if d.get("metadata_json"):
            try:
                d["metadata"] = json.loads(d["metadata_json"])
            except Exception:
                d["metadata"] = {}
        results.append(d)
    conn.close()
    return results

def get_vocab_from_cache(word: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT * FROM vocabulary WHERE LOWER(word) = LOWER(?)", (word.strip(),)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    return {
        "word": d["word"],
        "part_of_speech": d["part_of_speech"],
        "phonetic": d["phonetic"],
        "meanings": json.loads(d["meanings_json"]),
        "examples": json.loads(d["examples_json"]),
        "synonyms": json.loads(d["synonyms_json"] or "[]"),
        "antonyms": json.loads(d["antonyms_json"] or "[]"),
        "level": d["level"],
        "from_cache": True
    }

def save_vocab_to_cache(vocab_data: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR REPLACE INTO vocabulary 
           (word, part_of_speech, phonetic, meanings_json, examples_json, synonyms_json, antonyms_json, level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            vocab_data.get("word", "").lower().strip(),
            vocab_data.get("part_of_speech", ""),
            vocab_data.get("phonetic", ""),
            json.dumps(vocab_data.get("meanings", []), ensure_ascii=False),
            json.dumps(vocab_data.get("examples", []), ensure_ascii=False),
            json.dumps(vocab_data.get("synonyms", []), ensure_ascii=False),
            json.dumps(vocab_data.get("antonyms", []), ensure_ascii=False),
            vocab_data.get("level", "beginner")
        )
    )
    conn.commit()
    conn.close()

def log_api_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int, endpoint: str, status: str = "success"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO api_usage (provider, model, prompt_tokens, completion_tokens, total_tokens, endpoint, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (provider, model, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, endpoint, status)
    )
    conn.commit()
    conn.close()

def save_feedback(message_id: int, is_helpful: bool, comment: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback (message_id, is_helpful, comment) VALUES (?, ?, ?)",
        (message_id, is_helpful, comment)
    )
    f_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return f_id
