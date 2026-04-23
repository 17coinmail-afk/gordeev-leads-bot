import asyncio
import re
from datetime import datetime, timedelta

import database as db
from parsers import fetch_all_projects

_last_sent = {}
RATE_LIMIT_SECONDS = 120


def process_projects(projects: list) -> list:
    new_projects = []
    for p in projects:
        if not db.project_exists(p["link"]):
            db.add_project(
                link=p["link"],
                title=p["title"],
                description=p["description"],
                budget=p["budget"],
                source=p["source"],
                published_at=p["published_at"],
            )
            new_projects.append(p)
    return new_projects


async def send_to_user(application, user_id: int, projects: list, ai_notes: dict):
    from bot import format_project_message, format_digest, build_project_keyboard

    now = datetime.now()
    last = _last_sent.get(user_id)
    if last and (now - last).total_seconds() < RATE_LIMIT_SECONDS:
        return

    if not projects:
        return

    _last_sent[user_id] = now

    try:
        if len(projects) == 1:
            p = projects[0]
            text = format_project_message(p, ai_notes.get(p["link"], ""))
            kb = build_project_keyboard(p["link"])
            await application.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            db.log_sent(user_id, p["link"])

        elif 2 <= len(projects) <= 3:
            for p in projects:
                text = format_project_message(p, ai_notes.get(p["link"], ""))
                kb = build_project_keyboard(p["link"])
                await application.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
                db.log_sent(user_id, p["link"])

        else:
            text = format_digest(projects, ai_notes)
            await application.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            for p in projects:
                db.log_sent(user_id, p["link"])

    except Exception as e:
        print(f"Failed to send to {user_id}: {e}")


async def check_and_send(application):
    from ai import analyze_project

    print("[Scheduler] Checking projects...")
    projects = await fetch_all_projects()
    new_projects = process_projects(projects)
    print(f"[Scheduler] New projects found: {len(new_projects)}")

    if not new_projects:
        return

    ai_notes = {}
    to_analyze = new_projects[:10]
    if to_analyze:
        tasks = [analyze_project(p["title"], p["description"]) for p in to_analyze]
        results = await asyncio.gather(*tasks)
        for p, note in zip(to_analyze, results):
            if note:
                ai_notes[p["link"]] = note

    users = db.get_all_subscribed_users()
    for user in users:
        user_id, keywords, min_budget = user[0], user[1], user[2]
        is_pro = db.check_and_reset_pro(user_id)
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
            await send_to_user(application, user_id, matched, ai_notes)


async def remind_expiring_pro(application):
    """Напоминает за 3 дня до окончания Pro."""
    users = db.get_users_with_expiring_pro(days=3)
    for user_id in users:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="⏳ <b>Ваша Pro-подписка истекает через 3 дня!</b>\n\n"
                     "Чтобы не потерять доступ ко всем биржам, продлите подписку: /pay",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Failed to send reminder to {user_id}: {e}")


async def daily_cleanup(application):
    """Ежедневная очистка старых данных."""
    proj_deleted, logs_deleted = db.cleanup_old_data()
    print(f"[Cleanup] Deleted {proj_deleted} old projects, {logs_deleted} old logs")


async def health_check(application):
    """Если парсер 3 раза подряд вернул 0 проектов — пинг админу."""
    # Simple in-memory counter would need global state; skipping for now
    pass


def start_scheduler(application):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, "interval", minutes=10, args=[application])
    scheduler.add_job(remind_expiring_pro, "cron", hour=10, minute=0, args=[application])
    scheduler.add_job(daily_cleanup, "cron", hour=4, minute=0, args=[application])
    scheduler.start()
    return scheduler
