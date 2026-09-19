# 🎓 Study Bot - Trợ lý Học tập & Tra cứu Từ vựng Thông minh

Study Bot là trợ lý học tập đa nền tảng (Web & Telegram Bot) được phát triển bằng Python (FastAPI), tích hợp trí tuệ nhân tạo (Google Gemini / OpenAI) và cơ chế lưu đệm thông minh (SQLite Cache) để hỗ trợ học sinh, sinh viên học tập hiệu quả.

---

## ✨ Tính năng nổi bật

- 🤖 **Trợ lý gia sư AI**: Giải thích bài tập, khái niệm học thuật từng bước theo phương pháp sư phạm, tùy chỉnh theo cấp độ người học (`Beginner`, `Intermediate`, `Advanced`).
- 📖 **Tra cứu từ vựng đa năng**: 
  - Nghĩa tiếng Việt chi tiết, chuẩn ngữ cảnh.
  - Phiên âm chuẩn IPA & từ loại tiếng Việt/tiếng Anh.
  - Ví dụ minh họa song ngữ Anh - Việt thực tế.
  - Từ đồng nghĩa (Synonyms) & Trái nghĩa (Antonyms).
- ⚡ **Siêu tiết kiệm chi phí**: Tích hợp SQLite Cache giúp tra cứu từ vựng cực nhanh và không tốn token AI cho các từ đã tra.
- 📱 **Tích hợp đa nền tảng**:
  - **Giao diện Web**: Hiện đại, mượt mà, hỗ trợ Markdown và công thức Toán học KaTeX.
  - **Telegram Bot**: Hoạt động 24/7 với các lệnh tiện ích (`/start`, `/vocab <từ>`, `/level <cấp_độ>`).
- 🚀 **Tối ưu triển khai VPS**: Nhẹ nhàng, ổn định, hoạt động hoàn hảo trên VPS Linux chỉ từ 512MB - 1GB RAM.

---

## 📂 Cấu trúc dự án

```text
study-bot/
├── app/
│   ├── __init__.py
│   ├── config.py             # Cấu hình Pydantic & biến môi trường
│   ├── database.py           # SQLite database & cơ chế caching
│   ├── ai_service.py         # Kết nối Gemini / OpenAI & AI enrichment
│   ├── vocab_service.py      # Logic tra từ điển song ngữ
│   ├── security.py           # Rate limiting & làm sạch dữ liệu đầu vào
│   ├── telegram_bot.py       # Bot Telegram trực tuyến
│   └── main.py               # FastAPI Backend & RESTful APIs
├── deployment/
│   ├── deploy.sh             # Script cài đặt tự động 1-click trên VPS
│   ├── nginx.conf            # Cấu hình Nginx Reverse Proxy
│   ├── studybot.service      # Systemd service cho Web API
│   └── studybot-telegram.service # Systemd service cho Telegram Bot
├── static/
│   ├── index.html            # Giao diện Web
│   ├── style.css             # CSS thiết kế hiện đại
│   └── app.js                # Logic tương tác phía Client
├── .env.example              # File mẫu biến môi trường
├── requirements.txt          # Danh sách thư viện Python
├── test_bot.py               # Bộ kiểm thử tự động (Unit tests)
└── README_VPS.md             # Hướng dẫn chi tiết triển khai lên VPS
```

---

## 🛠️ Hướng dẫn cài đặt & Chạy cục bộ (Local)

### 1. Tạo môi trường ảo và cài đặt thư viện
```bash
python -m venv venv

# Kích hoạt trên Windows:
.\venv\Scripts\activate
# Kích hoạt trên Linux/macOS:
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Sao chép `.env.example` thành `.env`:
```bash
cp .env.example .env
```
Điền các thông tin cần thiết trong `.env`:
- `AI_PROVIDER=gemini` (hoặc `openai`)
- `GEMINI_API_KEY=...` (Lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/))
- `TELEGRAM_BOT_TOKEN=...` (Tạo từ [@BotFather](https://t.me/BotFather))

### 3. Chạy ứng dụng

- **Chạy Web Server:**
  ```bash
  python -m uvicorn app.main:app --port 8000 --reload
  ```
  Mở trình duyệt truy cập: `http://localhost:8000`

- **Chạy Telegram Bot:**
  ```bash
  python -m app.telegram_bot
  ```

---

## 🌐 Hướng dẫn triển khai lên VPS Linux (24/7)

Xem tài liệu hướng dẫn đầy đủ tại: **[README_VPS.md](README_VPS.md)**.
Dự án đã có sẵn script `deployment/deploy.sh` tự động cấu hình Nginx, Systemd, SSL và tường lửa UFW chỉ với một dòng lệnh.

---

## 🧪 Chạy Kiểm thử (Unit Tests)

```bash
python -m unittest test_bot.py
```
