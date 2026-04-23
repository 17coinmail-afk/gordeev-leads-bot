import os
import re
from io import BytesIO
from datetime import datetime

import qrcode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

SBP_PHONE = os.getenv("SBP_PHONE", "+79990000000")
SBP_BANK = os.getenv("SBP_BANK", "Тинькофф")
SBP_PRICE = int(os.getenv("SBP_PRICE", "500"))

# Антифлуд: user_id -> timestamp
_antiflood = {}
ANTIFLOOD_SECONDS = 1


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def check_antiflood(user_id: int) -> bool:
    now = datetime.now()
    last = _antiflood.get(user_id)
    if last and (now - last).total_seconds() < ANTIFLOOD_SECONDS:
        return False
    _antiflood[user_id] = now
    return True


def generate_payment_qr(user_id: int) -> BytesIO:
    text = (
        f"СБП перевод\n"
        f"Получатель: {SBP_PHONE}\n"
        f"Банк: {SBP_BANK}\n"
        f"Сумма: {SBP_PRICE} ₽\n"
        f"Назначение: Pro подписка ID{user_id}"
    )
    img = qrcode.make(text)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# === Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    db.add_user(user_id)

    args = context.args
    if args and args[0].startswith("ref"):
        try:
            ref_id = int(args[0].replace("ref", ""))
            if ref_id != user_id:
                conn = sqlite3.connect(db.DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref_id, user_id))
                conn.commit()
                conn.close()
                await context.bot.send_message(chat_id=ref_id, text="🎉 У вас новый реферал!")
        except Exception:
            pass

    await update.message.reply_text(
        "Привет! Я умный агрегатор фриланс-заказов.\n\n"
        "Я собираю заказы с FL.ru, Freelance.ru и Kwork,\n"
        "фильтрую по вашим навыкам и присылаю только лучшее.\n\n"
        "Нажмите /help, чтобы увидеть все команды.\n\n"
        "<b>Быстрый старт:</b> /subscribe → /setkeywords → /check",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return

    is_admin = user_id == ADMIN_USER_ID
    text = (
        "📖 <b>Справка по командам</b>\n\n"
        "<b>Пользовательские:</b>\n"
        "/start — Регистрация\n"
        "/setkeywords — Задать фильтры (через запятую)\n"
        "/setbudget — Минимальный бюджет\n"
        "/template — Сохранить шаблон отклика\n"
        "/subscribe — Включить уведомления\n"
        "/unsubscribe — Выключить уведомления\n"
        "/stats — Моя статистика\n"
        "/ref — Реферальная ссылка\n"
        "/pay — Купить Pro (QR-код СБП)\n"
        "/pro — Статус подписки\n"
        "/check — Проверить заказы сейчас\n"
        "/status — Мои настройки\n\n"
    )
    if is_admin:
        text += (
            "<b>Админские:</b>\n"
            "/admin — Панель управления\n"
            "/activate user_id days — Активировать Pro\n"
            "/broadcast текст — Рассылка всем\n"
            "/ban user_id — Заблокировать\n"
            "/unban user_id — Разблокировать\n"
        )
    await update.message.reply_text(text, parse_mode="HTML")


async def setkeywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id) or not check_antiflood(user_id):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Используй: /setkeywords python, бот, парсер")
        return
    db.set_keywords(user_id, text.lower())
    await update.message.reply_text(f"🔑 Ключевые слова: {text}")


async def setbudget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id) or not check_antiflood(user_id):
        return
    try:
        budget = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Используй: /setbudget 15000")
        return
    db.set_budget(user_id, budget)
    await update.message.reply_text(f"💰 Минимальный бюджет: {budget}")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    db.set_subscription(user_id, True)
    await update.message.reply_text(
        "🔔 Уведомления включены!\n\n"
        "Я буду присылать заказы каждые 10 минут. "
        "Если заказов много — сгруппирую в дайджест."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    db.set_subscription(user_id, False)
    await update.message.reply_text("🔕 Уведомления выключены.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Настройки не найдены. Напиши /start")
        return
    keywords, budget, subscribed = user[1], user[2], user[3]
    template = user[4] or "(не задан)"
    is_pro = db.check_and_reset_pro(user_id)
    pro_status = "💎 Pro" if is_pro else "⭐ Free"
    await update.message.reply_text(
        f"{pro_status}\n\n"
        f"🔑 Ключевые слова: {keywords or 'все'}\n"
        f"💰 Мин. бюджет: {budget}\n"
        f"📋 Шаблон: {template[:50]}{'...' if len(template) > 50 else ''}\n"
        f"🔔 Уведомления: {'вкл' if subscribed else 'выкл'}"
    )


async def set_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id) or not check_antiflood(user_id):
        return
    text = " ".join(context.args)
    if not text:
        current = db.get_template(user_id)
        await update.message.reply_text(
            f"📋 Текущий шаблон:\n<code>{escape_html(current or 'не задан')}</code>\n\n"
            f"Чтобы изменить:\n/template Здравствуйте! Готов выполнить...",
            parse_mode="HTML",
        )
        return
    db.set_template(user_id, text)
    await update.message.reply_text("✅ Шаблон отклика сохранён!")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    total, today = db.get_user_stats(user_id)
    is_pro = db.check_and_reset_pro(user_id)
    status_text = "💎 Pro" if is_pro else "⭐ Free (жмите /pay)"
    await update.message.reply_text(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"{status_text}\n"
        f"Всего получено заказов: {total}\n"
        f"Сегодня: {today}\n\n"
        f"Настройте фильтры (/setkeywords), чтобы получать только релевантные.",
        parse_mode="HTML",
    )


async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    user = db.get_user(user_id)
    code = user[5] if user else f"ref{user_id}"
    bot_username = context.bot.username
    link = f"https://t.me/{bot_username}?start={code}"
    await update.message.reply_text(
        f"🎁 <b>Ваша реферальная ссылка</b>\n\n"
        f"{link}\n\n"
        f"Отправьте её друзьям. За каждого приглашённого — +3 дня Pro!",
        parse_mode="HTML",
    )


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    qr_buf = generate_payment_qr(user_id)
    caption = (
        f"💎 <b>Pro-подписка</b>\n\n"
        f"Стоимость: <b>{SBP_PRICE} ₽/мес</b>\n\n"
        f"Что входит:\n"
        f"• Все 3 биржи (FL.ru, Freelance.ru, Kwork)\n"
        f"• AI-анализ заказов\n"
        f"• Неограниченные фильтры\n"
        f"• Максимальная скорость\n\n"
        f"<b>Как оплатить:</b>\n"
        f"1. Отсканируйте QR-код\n"
        f"2. Или переведите по СБП на <code>{SBP_PHONE}</code> ({SBP_BANK})\n"
        f"3. В комментарии: <code>Pro {user_id}</code>\n"
        f"4. Подписка активируется автоматически за 1–3 мин\n\n"
        f"Если что-то пошло не так — пишите админу.",
    )
    await update.message.reply_photo(photo=qr_buf, caption=caption[0], parse_mode="HTML")


async def pro_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id):
        return
    is_pro = db.check_and_reset_pro(user_id)
    user = db.get_user(user_id)
    if is_pro and user and user[8]:
        until = user[8][:10]
        await update.message.reply_text(
            f"💎 <b>Pro активна</b> до {until}\n\n"
            f"Вам доступны все функции.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"⭐ <b>Бесплатный тариф</b>\n\n"
            f"Доступно:\n"
            f"• Только FL.ru\n"
            f"• Базовые фильтры\n\n"
            f"Хотите больше? Нажмите /pay",
            parse_mode="HTML",
        )


async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Только для администратора.")
        return
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Используй: /activate user_id days\nПример: /activate 12345678 30")
        return
    db.activate_pro(target_id, days)
    await update.message.reply_text(f"✅ Pro для <code>{target_id}</code> на {days} дней.", parse_mode="HTML")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 Pro активирована на {days} дней!\n\nТеперь вам доступны все 3 биржи и AI-анализ.",
        )
    except Exception as e:
        print(f"Failed to notify {target_id}: {e}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Используй: /broadcast Ваш текст сообщения")
        return

    users = db.get_all_users()
    sent = 0
    failed = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"📨 Рассылка завершена. Отправлено: {sent}, ошибок: {failed}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Используй: /ban user_id")
        return
    db.ban_user(target_id)
    await update.message.reply_text(f"🚫 Пользователь <code>{target_id}</code> заблокирован.", parse_mode="HTML")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Используй: /unban user_id")
        return
    db.unban_user(target_id)
    await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> разблокирован.", parse_mode="HTML")


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Только для администратора.")
        return
    total, active, pro_users, banned, projects, sent_today = db.get_admin_stats()
    await update.message.reply_text(
        f"👑 <b>Админ-панель</b>\n\n"
        f"👤 Всего: {total}\n"
        f"🔔 Активных: {active}\n"
        f"💎 Pro: {pro_users}\n"
        f"🚷 Заблокировано: {banned}\n"
        f"📦 Заказов в базе: {projects}\n"
        f"📨 Уведомлений сегодня: {sent_today}\n\n"
        f"Команды:\n"
        f"/activate user_id days\n"
        f"/broadcast текст\n"
        f"/ban user_id /unban user_id",
        parse_mode="HTML",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "hide":
        await query.delete_message()
    elif data == "template":
        template = db.get_template(user_id)
        if template:
            await query.message.reply_text(
                f"📋 <b>Ваш шаблон:</b>\n<code>{escape_html(template)}</code>",
                parse_mode="HTML",
            )
        else:
            await query.message.reply_text(
                "📋 Шаблон не задан. Задайте:\n/template Здравствуйте! Готов выполнить..."
            )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Нажмите /help для списка команд.")


# === Formatting ===

def build_project_keyboard(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 Открыть заказ", url=link)],
            [
                InlineKeyboardButton("📋 Мой отклик", callback_data="template"),
                InlineKeyboardButton("❌ Скрыть", callback_data="hide"),
            ],
        ]
    )


def format_project_message(p: dict, ai_note: str = "") -> str:
    title = escape_html(p["title"][:200])
    budget = escape_html(p["budget"])
    source = p["source"].upper()

    budget_emoji = "💰"
    nums = re.findall(r"\d+", p["budget"].replace(" ", "").replace("\xa0", ""))
    if nums:
        try:
            b = int(nums[0])
            if b >= 50000:
                budget_emoji = "🔥"
            elif b >= 20000:
                budget_emoji = "💎"
        except:
            pass

    lines = [
        f"{budget_emoji} <b>{title}</b>",
        f"💵 Бюджет: {budget}",
        f"📍 Источник: {source}",
    ]
    if ai_note:
        lines.append(f"💡 <i>{escape_html(ai_note)}</i>")

    return "\n".join(lines)


def format_digest(projects: list, ai_notes: dict) -> str:
    lines = [f"📦 <b>Дайджест заказов ({len(projects)} новых)</b>\n"]
    for i, p in enumerate(projects[:10], 1):
        title = escape_html(p["title"][:60])
        budget = escape_html(p["budget"])
        note = ai_notes.get(p["link"], "")
        note_str = f" — <i>{escape_html(note)}</i>" if note else ""
        lines.append(f"{i}. {title} ({budget}){note_str}")
    if len(projects) > 10:
        lines.append(f"\n...и ещё {len(projects) - 10}")
    return "\n".join(lines)


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_banned(user_id) or not check_antiflood(user_id):
        return

    await update.message.reply_text("🔍 Проверяю заказы, секунду...")

    from parsers import fetch_all_projects
    from scheduler import process_projects

    projects = await fetch_all_projects()
    new_projects = process_projects(projects)

    is_pro = db.check_and_reset_pro(user_id)
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала напиши /start")
        return

    keywords, min_budget = user[1], user[2]
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    matched = []
    for p in new_projects:
        if not is_pro and p["source"] != "fl":
            continue
        text = (p["title"] + " " + p["description"]).lower()
        if keywords_list:
            if not any(k in text for k in keywords_list):
                continue
        nums = re.findall(r"\d+", p["budget"].replace(" ", "").replace("\xa0", ""))
        if nums:
            try:
                b = int(nums[0])
                if b < min_budget:
                    continue
            except Exception:
                pass
        matched.append(p)

    if matched:
        for p in matched[:3]:
            await update.message.reply_text(
                format_project_message(p),
                parse_mode="HTML",
                reply_markup=build_project_keyboard(p["link"]),
                disable_web_page_preview=True,
            )
        if len(matched) > 3:
            await update.message.reply_text(f"И ещё {len(matched) - 3} подходящих заказов.")
    else:
        await update.message.reply_text("Новых подходящих заказов не найдено.")


def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setkeywords", setkeywords))
    application.add_handler(CommandHandler("setbudget", setbudget))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("template", set_template))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("ref", referral))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("pro", pro_status))
    application.add_handler(CommandHandler("check", check_now))
    application.add_handler(CommandHandler("activate", activate))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    return application
