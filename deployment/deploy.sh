#!/bin/bash
# ==============================================================================
# Script cài đặt tự động Study Bot trên VPS Linux (Ubuntu / Debian)
# ==============================================================================

set -e

echo "🚀 Bắt đầu quá trình thiết lập Study Bot trên Linux VPS..."

# 1. Cập nhật hệ thống và cài đặt công cụ cần thiết
echo "📦 Cập nhật gói hệ thống..."
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx curl git ufw

# 2. Tạo thư mục làm việc chuẩn
INSTALL_DIR="/var/www/study-bot"
echo "📁 Chuẩn bị thư mục ứng dụng tại $INSTALL_DIR..."
sudo mkdir -p $INSTALL_DIR
sudo chown -R $USER:$USER $INSTALL_DIR

# Copy toàn bộ file hiện tại vào $INSTALL_DIR (kể cả file ẩn)
if [ "$(pwd)" != "$INSTALL_DIR" ]; then
    cp -a ./. $INSTALL_DIR/
fi

cd $INSTALL_DIR

# 3. Tạo môi trường ảo Python và cài thư viện
echo "🐍 Tạo môi trường ảo Python (venv)..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Kiểm tra file .env
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "⚠️ Chưa tìm thấy file .env, tạo file mẫu từ .env.example..."
    if [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    else
        touch "$INSTALL_DIR/.env"
    fi
    echo "👉 Vui lòng mở file .env và điền GEMINI_API_KEY hoặc OPENAI_API_KEY!"
fi

# 5. Cài đặt Systemd Services (Web API và Telegram Bot)
echo "⚙️ Thiết lập Systemd Services để hệ thống chạy ngầm 24/7..."
sudo cp deployment/studybot.service /etc/systemd/system/studybot.service
sudo cp deployment/studybot-telegram.service /etc/systemd/system/studybot-telegram.service
sudo systemctl daemon-reload
sudo systemctl enable studybot
sudo systemctl restart studybot
sudo systemctl enable studybot-telegram
sudo systemctl restart studybot-telegram

# 6. Cài đặt Nginx Reverse Proxy
echo "🌐 Thiết lập Nginx..."
sudo cp deployment/nginx.conf /etc/nginx/sites-available/studybot
sudo ln -sf /etc/nginx/sites-available/studybot /etc/nginx/sites-enabled/
# Xóa site default nếu cần
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 7. Mở cổng Firewall (UFW)
echo "🛡️ Cấu hình Firewall UFW..."
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw --force enable

echo "=============================================================================="
echo "🎉 CHÚC MỪNG! Study Bot đã được cài đặt và kích hoạt thành công!"
echo "📍 Kiểm tra trạng thái: sudo systemctl status studybot"
echo "📍 Xem log trực tiếp:   journalctl -u studybot -f"
echo "🌐 Truy cập qua trình duyệt: http://<IP_VPS_CUA_BAN>"
echo "=============================================================================="
