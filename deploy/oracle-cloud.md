# Хостинг на Oracle Cloud Free Tier

**Что это:** Настоящий VPS (виртуальный сервер), который работает 24/7. Всегда бесплатно. Дают 1 GB RAM + 2 CPU — достаточно для нашего бота.

---

## 1. Регистрация

1. Открой https://www.oracle.com/cloud/free/
2. Нажми **Start for free**
3. Заполни данные (можно российские)
4. Укажи карту Visa/MasterCard (списывают и возвращают ~50 руб для проверки)
5. Дождись активации (обычно 5–15 минут, иногда до 24 часов)

---

## 2. Создание сервера (VM)

1. Войди в консоль Oracle Cloud
2. Меню → **Compute** → **Instances**
3. Нажми **Create instance**
4. **Name:** `freelance-bot`
5. **Image:** Ubuntu 22.04 (в разделе "Image and shape" выбери **Change image** → Ubuntu 22.04)
6. **Shape:** **VM.Standard.E2.1.Micro** (это Always Free, 1/8 OCPU + 1 GB RAM)
7. **Networking:** создай новую VCN или используй существующую
8. **SSH keys:** выбери **Generate SSH key pair** → скачай приватный ключ (`*.key`)
9. Нажми **Create**

Жди 1–2 минуты, пока статус станет **RUNNING**.

---

## 3. Открытие портов

По умолчанию Oracle блокирует весь трафик.

1. В Instances нажми на имя сервера
2. Слева найди **Subnet** → нажми на ссылку подсети
3. Найди **Default Security List** → кликни
4. Нажми **Add Ingress Rules**
5. Заполни:
   - Source Type: `CIDR`
   - Source CIDR: `0.0.0.0/0`
   - Protocol: `All`
6. Сохрани

> Примечание: для Telegram polling достаточно исходящего соединения, но так сервер станет доступен по SSH из любой точки.

---

## 4. Подключение по SSH

**Windows (PowerShell):**
```powershell
# Права на ключ
icacls "C:\Users\ТЫ\Downloads\ssh-key.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"

# Подключение
ssh -i "C:\Users\ТЫ\Downloads\ssh-key.key" ubuntu@ВНЕШНИЙ_IP_СЕРВЕРА
```

**Linux/Mac:**
```bash
chmod 600 ~/Downloads/ssh-key.key
ssh -i ~/Downloads/ssh-key.key ubuntu@ВНЕШНИЙ_IP_СЕРВЕРА
```

Внешний IP виден в консоли Oracle (Public IP Address).

---

## 5. Загрузка проекта

**На вашем компьютере** открой PowerShell в папке проекта и выполни:

```powershell
# Копируем все файлы на сервер
scp -i "C:\Users\ТЫ\Downloads\ssh-key.key" -r . ubuntu@ВНЕШНИЙ_IP:/home/ubuntu/freelance-bot
```

**На сервере** (в SSH-сессии):
```bash
sudo mv /home/ubuntu/freelance-bot /opt/freelance-bot
sudo chown -R ubuntu:ubuntu /opt/freelance-bot
cd /opt/freelance-bot
```

---

## 6. Запуск установки

```bash
cd /opt/freelance-bot
chmod +x deploy/setup.sh
./deploy/setup.sh
```

Скрипт установит Python, зависимости, Chromium для Playwright и настроит systemd.

---

## 7. Настройка .env

```bash
nano /opt/freelance-bot/.env
```

Вставь свои токены (см. `.env.example`):
```
BOT_TOKEN=...
ADMIN_USER_ID=...
SBP_PHONE=...
IMAP_USER=...
```

Сохрани: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

## 8. Запуск бота

```bash
sudo systemctl start freelance-bot
sudo systemctl status freelance-bot
```

Смотри логи в реальном времени:
```bash
sudo journalctl -u freelance-bot -f
```

---

## 9. Автозапуск

Systemd уже настроен на автозапуск. Если сервер перезагрузится, бот стартует сам:
```bash
sudo systemctl enable freelance-bot
```

---

## 10. Обновление бота

Если ты изменил код locally:

```powershell
# На Windows — заливаем обновления
scp -i "ssh-key.key" -r . ubuntu@IP:/home/ubuntu/freelance-bot-new
```

```bash
# На сервере
sudo systemctl stop freelance-bot
sudo rm -rf /opt/freelance-bot
sudo mv /home/ubuntu/freelance-bot-new /opt/freelance-bot
sudo chown -R ubuntu:ubuntu /opt/freelance-bot
cd /opt/freelance-bot
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
sudo systemctl start freelance-bot
```

---

## Памятка команд

| Команда | Действие |
|---------|----------|
| `sudo systemctl start freelance-bot` | Запустить |
| `sudo systemctl stop freelance-bot` | Остановить |
| `sudo systemctl restart freelance-bot` | Перезапустить |
| `sudo systemctl status freelance-bot` | Статус |
| `sudo journalctl -u freelance-bot -f` | Логи в реальном времени |

---

## Если кончилась память (1 GB)

Playwright + Chromium жрут память. Если бот падает с OOM:

```bash
# Добавить swap на 2 GB
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
sudo swapon --show
```

Для автоматического подключения swap после перезагрузки:
```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
