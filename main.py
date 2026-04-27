import asyncio
import os
import traceback

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
    try:
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
                print(f"[PAYMENT] Failed to notify user {user_id}: {e}")
    except Exception as e:
        print(f"[PAYMENT] Auto payment check error: {e}")
        traceback.print_exc()


async def main():
    print("[MAIN] === Starting up ===")

    # 1. Database
    try:
        db.init_db()
        print("[MAIN] Database initialized OK")
    except Exception as e:
        print(f"[MAIN] Database init FAILED: {e}")
        traceback.print_exc()
        raise

    # 2. Bot application
    try:
        application = run_bot()
        print("[MAIN] Bot application created OK")
    except Exception as e:
        print(f"[MAIN] Bot creation FAILED: {e}")
        traceback.print_exc()
        raise

    # 3. Dashboard
    try:
        port = int(os.getenv("PORT", "8080") or "8080")
        run_dashboard(port)
        print(f"[MAIN] Dashboard running on port {port}")
    except Exception as e:
        print(f"[MAIN] Dashboard start FAILED: {e}")
        traceback.print_exc()

    # 4. Initialize application
    try:
        await application.initialize()
        print("[MAIN] Application initialized OK")
    except Exception as e:
        print(f"[MAIN] Application initialize FAILED: {e}")
        traceback.print_exc()
        raise

    # 5. Start application
    try:
        await application.start()
        print("[MAIN] Application started OK")
    except Exception as e:
        print(f"[MAIN] Application start FAILED: {e}")
        traceback.print_exc()
        raise

    # 6. Start polling
    try:
        await application.updater.start_polling()
        print("[MAIN] Bot polling started OK")
    except Exception as e:
        print(f"[MAIN] FAILED to start polling: {e}")
        traceback.print_exc()
        raise

    # 7. Initial checks
    try:
        await check_and_send(application)
        print("[MAIN] Initial check_and_send completed")
    except Exception as e:
        print(f"[MAIN] Initial check_and_send FAILED: {e}")
        traceback.print_exc()

    try:
        await auto_payment_check(application)
        print("[MAIN] Initial payment check completed")
    except Exception as e:
        print(f"[MAIN] Initial payment check FAILED: {e}")
        traceback.print_exc()

    # 8. Schedulers
    try:
        job_scheduler = start_scheduler(application)
        print("[MAIN] Job scheduler started")
    except Exception as e:
        print(f"[MAIN] Job scheduler FAILED: {e}")
        traceback.print_exc()
        job_scheduler = None

    try:
        payment_scheduler = AsyncIOScheduler()
        payment_scheduler.add_job(auto_payment_check, "interval", minutes=3, args=[application])
        payment_scheduler.start()
        print("[MAIN] Payment scheduler started")
    except Exception as e:
        print(f"[MAIN] Payment scheduler FAILED: {e}")
        traceback.print_exc()
        payment_scheduler = None

    print("[MAIN] === Bot is fully running. Waiting for messages... ===")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("[MAIN] Shutting down...")
    finally:
        if job_scheduler:
            try:
                job_scheduler.shutdown()
            except Exception:
                pass
        if payment_scheduler:
            try:
                payment_scheduler.shutdown()
            except Exception:
                pass
        try:
            await application.updater.stop()
        except Exception:
            pass
        await application.stop()
        await application.shutdown()
        print("[MAIN] Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[MAIN] FATAL ERROR during startup: {e}")
        traceback.print_exc()
        raise
