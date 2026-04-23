# Запуск на своём компьютере (self-hosted)

Если у вас есть компьютер, который работает 24/7 (или Raspberry Pi), проще всего запустить бота дома.

## Windows

### 1. Установка
```powershell
# Установи Python 3.10+ с python.org
pip install -r requirements.txt
playwright install chromium
```

### 2. Создай .env
Скопируй `.env.example` в `.env` и заполни.

### 3. Запуск
```powershell
$env:BOT_TOKEN="..."
$env:ADMIN_USER_ID="..."
# ... остальные переменные
python main.py
```

### 4. Автозапуск (через Планировщик задач)
1. Win+R → `taskschd.msc`
2. Действие → Создать задачу
3. Общие: «Запускать при входе в систему», «Выполнять независимо от регистрации пользователя»
4. Триггеры: «При запуске»
5. Действие: `python.exe`, аргументы: `C:\Users\ТЫ\Desktop\Автофинансирование\freelance_bot\main.py`
6. Условия: снять галку «Останавливать при простое»

## Linux / Raspberry Pi

```bash
cd ~/freelance-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Создать .env
nano .env

# Запуск в фоне через tmux
tmux new -s bot
python main.py
# Ctrl+B, D — отключиться

# Переподключиться: tmux attach -t bot
```

## Для чего это подходит

- ✅ Быстрый старт без регистраций
- ✅ Не нужна карта
- ✅ Полный контроль
- ❌ Компьютер должен быть включен
- ❌ Нет статического IP (но для Telegram polling это не важно)
