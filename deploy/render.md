# Деплой на Render.com (бесплатный тариф)

Render — облачный хостинг с бесплатным тарифом. Подходит для запуска бота 24/7.

## Важно про free tier

- **RAM:** 512 MB (для Playwright/Chromium может не хватить)
- **Sleep:** приложение "засыпает" через 15 минут без HTTP-трафика
- **Решение:** UptimeRobot пингует дашборд каждые 5 минут → приложение не уснет

> **Kwork** на Render может не работать из-за нехватки памяти. FL.ru и Freelance.ru работают стабильно.

---

## 1. Подготовка

1. Создай репозиторий на GitHub и залей туда проект:
```bash
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/ТВОЙ_НИК/gordeev-leads-bot.git
git push -u origin main
```

2. Зарегистрируйся на https://render.com (через GitHub)

---

## 2. Создание сервиса

1. В Render нажми **New +** → **Web Service**
2. Подключи свой GitHub-репозиторий
3. Заполни:
   - **Name:** `gordeev-leads-bot`
   - **Runtime:** Python
   - **Build Command:**
     ```bash
     pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium || true
     ```
   - **Start Command:** `python main.py`
4. Нажми **Create Web Service**

---

## 3. Переменные окружения

В разделе **Environment** добавь:

```
BOT_TOKEN=твой_токен
ADMIN_USER_ID=твой_id
SBP_PHONE=+79990000000
SBP_BANK=Тинькофф
SBP_PRICE=500
IMAP_SERVER=imap.gmail.com
IMAP_USER=email@gmail.com
IMAP_PASS=пароль_приложения
OPENAI_API_KEY=sk-...
```

---

## 4. Анти-sleep (критично!)

Без этого бот уснет через 15 минут.

1. Зарегистрируйся на https://uptimerobot.com
2. Добавь монитор:
   - **Type:** HTTP(s)
   - **URL:** `https://gordeev-leads-bot.onrender.com` (твой URL из Render)
   - **Interval:** 5 minutes
3. Сохрани

UptimeRobot будет пинговать дашборд каждые 5 минут, и Render не усыпит приложение.

---

## 5. Проверка

- Открой дашборд: `https://gordeev-leads-bot.onrender.com`
- Напиши боту в Telegram `/start`
- Проверь `/stats` и `/check`

---

## Проблемы

| Проблема | Решение |
|----------|---------|
| Playwright не ставится | Нормально, Kwork просто не будет парситься |
| R15 (Memory quota exceeded) | Убери Kwork из `parsers.py` или перейди на платный тариф |
| Бот не отвечает | Проверь логи в Render Dashboard → Logs |
