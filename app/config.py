import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm và load file .env từ thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    BASE_DIR: Path = BASE_DIR
    DB_PATH: Path = BASE_DIR / "study_bot.db"
    
    # AI Configuration
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Network & Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-studybot-secret-key-32chars")
    
    # Limits & Security
    MAX_MESSAGES_PER_MINUTE: int = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "30"))
    MAX_INPUT_LENGTH: int = int(os.getenv("MAX_INPUT_LENGTH", "1500"))
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Supported Study Levels
    VALID_LEVELS = ["beginner", "intermediate", "advanced"]
    
    # System Prompts & Boundaries
    PROHIBITED_TOPICS = [
        "lộ đề thi", "hack điểm", "làm hộ bài thi", "gian lận thi cử",
        "cheat exam", "bypass exam", "viết bài thi trọn gói"
    ]

settings = Settings()
