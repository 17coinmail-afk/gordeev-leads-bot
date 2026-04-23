#!/bin/bash
set -e

PROJECT_DIR="/opt/freelance-bot"
SERVICE_NAME="freelance-bot"

echo "=========================================="
echo "  Freelance Bot - Server Setup"
echo "=========================================="

# 1. System update
echo "[1/8] Updating system..."
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
echo "[2/8] Installing Python, git, and system deps..."
sudo apt install -y \
    python3 python3-pip python3-venv python3-dev \
    git curl wget \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 \
    fonts-liberation libappindicator3-1

# 3. Create project directory
echo "[3/8] Creating project directory..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown "$USER:$USER" "$PROJECT_DIR"

if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo "WARNING: Project files not found in $PROJECT_DIR"
    echo "Upload files first: scp -r . ubuntu@IP:/opt/freelance-bot"
    exit 1
fi

cd "$PROJECT_DIR"

# 4. Create virtual environment
echo "[4/8] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 5. Install Python packages
echo "[5/8] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Install Playwright browsers
echo "[6/8] Installing Playwright Chromium..."
playwright install chromium
playwright install-deps chromium

# 7. Setup systemd service
echo "[7/8] Setting up systemd service..."
sudo cp deploy/freelance-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# 8. Setup daily backup cron
echo "[8/8] Setting up daily backup..."
(crontab -l 2>/dev/null; echo "0 3 * * * $PROJECT_DIR/deploy/backup.sh >> /var/log/freelance-bot-backup.log 2>&1") | crontab -

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Create .env:       nano $PROJECT_DIR/.env"
echo "2. Start bot:         sudo systemctl start $SERVICE_NAME"
echo "3. Check status:      sudo systemctl status $SERVICE_NAME"
echo "4. View logs:         sudo journalctl -u $SERVICE_NAME -f"
echo "5. Dashboard:         http://YOUR_IP:8080"
echo ""
echo "Backup runs daily at 03:00 via cron"
