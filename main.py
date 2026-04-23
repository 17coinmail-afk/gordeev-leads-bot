import asyncio
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

import database as db
from bot import run_bot
from dashboard import run_dashboard
from payments import check_email_payments
from scheduler import check_and_send, start_scheduler

SBP_PRICE = int(os.getenv("SBP_PRICE", "500") or "500")


async def auto_payment_check(application):
    loop = asyncio.get_event_loop()
    user_ids = await loop.run_in_executor(None, check_email_payments)
    for user_id in user_ids:
        db.activate_pro(user_id, 30)
        db.mark_payment_processed(user_id, SBP_PRICE, "email")
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="🎉 <b>Pro активирована автоматически!</b>\n\n"
                     "Срок: 30 дней\n"
                     "Теперь доступны все 3 биржи и AI-анализ.",
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")


async def main():
    db.init_db()
    application = run_bot()

    # Запускаем веб-дашборд (порт из env для Render/Railway)
    port = int(os.getenv("PORT", "8080"))
    run_dashboard(port)
    print(f"Dashboard running on http://0.0.0.0:{port}")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Bot started. Press Ctrl+C to stop.")

    await check_and_send(application)
    await auto_payment_check(application)

    job_scheduler = start_scheduler(application)

    payment_scheduler = AsyncIOScheduler()
    payment_scheduler.add_job(auto_payment_check, "interval", minutes=3, args=[application])
    payment_scheduler.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down...")
    finally:
        job_scheduler.shutdown()
        payment_scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
