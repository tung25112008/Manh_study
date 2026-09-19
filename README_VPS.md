# Hướng dẫn chi tiết triển khai Study Bot trên VPS Linux (Ubuntu / Debian)

Tài liệu này hướng dẫn bạn từng bước đưa **Study Bot (Bot hỗ trợ học tập & Tra cứu từ vựng)** lên máy chủ ảo VPS Linux (Ubuntu 20.04 / 22.04 / 24.04 hoặc Debian 11 / 12) để bot hoạt động ổn định 24/7 mà không lo bị tắt khi bạn đóng máy tính cá nhân.

---

## 📋 Yêu cầu cấu hình tối thiểu
* **Hệ điều hành:** Ubuntu 20.04 / 22.04 LTS hoặc Debian 11 / 12.
* **CPU:** 1 Core vCPU.
* **RAM:** 512MB – 1GB RAM (rất tiết kiệm, hoạt động mượt mà).
* **Ổ cứng:** 5GB dung lượng trống.
* **Mạng:** Đã mở cổng 80 (HTTP) và 443 (HTTPS) trên firewall nhà cung cấp VPS (AWS, DigitalOcean, Linode, Vultr, Vietnix, TinoHost...).

---

## 🚀 Cách 1: Cài đặt tự động bằng Script (Khuyên dùng - Nhanh nhất)

Nếu bạn vừa tạo VPS mới, chỉ cần kết nối SSH vào VPS và chạy lệnh:

```bash
# 1. Tải thư mục study-bot lên VPS (hoặc git clone)
cd /root/study-bot

# 2. Cấp quyền thực thi và chạy script cài đặt
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

Script sẽ tự động:
- Cài đặt Python3, pip, venv, Nginx, UFW.
- Thiết lập môi trường ảo và cài toàn bộ thư viện cần thiết.
- Cấu hình `systemd` để bot tự chạy ngầm và tự khởi động cùng VPS.
- Cấu hình Nginx Reverse Proxy đưa cổng `8000` ra cổng `80`.

---

## 🛠️ Cách 2: Cài đặt thủ công từng bước

Nếu bạn muốn tự tay kiểm soát từng bước, hãy làm theo hướng dẫn dưới đây:

### Bước 1: Đăng nhập SSH vào VPS
Từ máy tính của bạn (Terminal trên Mac/Linux hoặc PowerShell trên Windows):
```bash
ssh root@<IP_VPS_CUA_BAN>
```

### Bước 2: Cập nhật hệ thống & Cài đặt gói cơ bản
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git nginx ufw curl
```

### Bước 3: Tạo thư mục chứa ứng dụng
```bash
sudo mkdir -p /var/www/study-bot
sudo chown -R $USER:$USER /var/www/study-bot
cd /var/www/study-bot
```

### Bước 4: Đưa mã nguồn lên VPS
Bạn có thể dùng một trong các cách sau:
* **Cách A (Dùng SCP từ máy tính):**
  ```powershell
  # Chạy trên PowerShell máy tính cá nhân của bạn:
  scp -r "C:\Users\Minh Tung\.gemini\antigravity-ide\scratch\study-bot\*" root@<IP_VPS>:/var/www/study-bot/
  ```
* **Cách B (Dùng Git):** Đẩy code lên GitHub cá nhân rồi `git clone` về thư mục `/var/www/study-bot`.

### Bước 5: Tạo môi trường ảo & Cài đặt thư viện
```bash
cd /var/www/study-bot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 6: Cấu hình file `.env`
Tạo file `.env` từ file mẫu:
```bash
cp .env.example .env
nano .env
```
Chỉnh sửa thông số:
* `AI_PROVIDER=gemini`
* `GEMINI_API_KEY=AIzaSy...` (Lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/))
* Hoặc nếu dùng OpenAI: `AI_PROVIDER=openai` và điền `OPENAI_API_KEY=sk-...`
* Bấm `Ctrl + O` -> `Enter` để lưu, `Ctrl + X` để thoát `nano`.

### Bước 7: Chạy thử nghiệm
Kiểm tra xem bot có khởi động được không:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Mở trình duyệt gõ: `http://<IP_VPS_CUA_BAN>:8000` để xem giao diện web.
Sau khi thấy chạy tốt, bấm `Ctrl + C` để tắt và chuyển sang cấu hình chạy ngầm 24/7.

---

## 🔄 Cấu hình chạy ngầm 24/7 với `systemd`

Để cả Web Server và Telegram Bot tự chạy ngầm 24/7 và tự khởi động lại khi VPS reboot:

1. Copy file cấu hình services vào hệ thống:
```bash
sudo cp deployment/studybot.service /etc/systemd/system/studybot.service
sudo cp deployment/studybot-telegram.service /etc/systemd/system/studybot-telegram.service
```

2. Tải lại cấu hình systemd và kích hoạt cả 2 service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable studybot studybot-telegram
sudo systemctl start studybot studybot-telegram
```

3. Kiểm tra trạng thái:
```bash
sudo systemctl status studybot
sudo systemctl status studybot-telegram
```
*(Nếu thấy cả 2 đều hiện màu xanh lá `active (running)` là cả Web Server và Telegram Bot đã hoạt động ngầm thành công!)*

---

## 🌐 Cấu hình Nginx & Cài SSL (HTTPS Miễn phí)

### 1. Cấu hình Nginx Reverse Proxy
```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/studybot
sudo ln -sf /etc/nginx/sites-available/studybot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```
Lúc này bạn đã có thể truy cập qua cổng 80 bình thường: `http://<IP_VPS_CUA_BAN>` mà không cần gõ `:8000`.

### 2. Cài SSL HTTPS miễn phí với Certbot (Nếu bạn đã gắn Tên Miền)
Nếu bạn có trỏ tên miền (ví dụ: `study.yourdomain.com`) về IP VPS:
```bash
# Sửa lại server_name trong /etc/nginx/sites-available/studybot thành tên miền của bạn
sudo nano /etc/nginx/sites-available/studybot

# Cài đặt Certbot và sinh chứng chỉ SSL tự động
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d study.yourdomain.com
```
Certbot sẽ tự động cấu hình HTTPS và tự động gia hạn chứng chỉ mỗi 90 ngày.

---

## 🛡️ Các lệnh quản trị hàng ngày

| Hành động | Lệnh thực hiện |
| :--- | :--- |
| **Xem log Web Server trực tiếp** | `journalctl -u studybot -f` |
| **Xem log Telegram Bot trực tiếp** | `journalctl -u studybot-telegram -f` |
| **Kiểm tra trạng thái hệ thống** | `sudo systemctl status studybot studybot-telegram` |
| **Khởi động lại cả 2 bot** | `sudo systemctl restart studybot studybot-telegram` |
| **Tạm dừng bot** | `sudo systemctl stop studybot studybot-telegram` |
| **Khởi động lại Nginx** | `sudo systemctl restart nginx` |
| **Sao lưu cơ sở dữ liệu** | `cp /var/www/study-bot/study_bot.db /var/www/study-bot/study_bot_backup.db` |

---

## 💡 Mẹo tối ưu cho VPS RAM thấp (512MB - 1GB)

Nếu thuê VPS gói rẻ (chỉ có 512MB hoặc 1GB RAM), bạn nên tạo **Swap File (RAM ảo)** 2GB để phòng trường hợp hệ điều hành bị quá tải (Out of Memory):

```bash
# Tạo swap file 2GB
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Giữ swap tồn tại sau khi reboot
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
Sau khi tạo Swap, VPS của bạn sẽ chạy cực kỳ ổn định và không bao giờ lo bị crash do thiếu RAM!
