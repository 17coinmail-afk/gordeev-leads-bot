import email
import imaplib
import os
import re
from datetime import datetime

import database as db

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER", "")
MAP_PASS = os.getenv("IMAP_PASS", "")
SBP_PRICE = int(os.getenv("SBP_PRICE", "500") or "500")


def _decode_subject(subject: str) -> str:
    """Декодирует Subject из RFC2047"""
    try:
        parts = email.header.decode_header(subject)
        decoded = ""
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded += part.decode(charset or "utf-8", errors="ignore")
            else:
                decoded += part
        return decoded
    except Exception:
        return subject


def _get_body(msg) -> str:
    """Извлекает текст из email"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="ignore")
            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload and not body:
                    # Если нет plain text, берем HTML и убираем теги грубо
                    html = payload.decode("utf-8", errors="ignore")
                    body += re.sub(r"<[^>]+>", " ", html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")
    return body


def check_email_payments() -> list:
    """
    Проверяет email на наличие входящих переводов.
    Возвращает список user_id, для которых найдены платежи.
    """
    if not IMAP_USER or not IMAP_PASS:
        return []

    found_users = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        # Ищем непрочитанные письма
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.close()
            mail.logout()
            return []

        for num in messages[0].split():
            try:
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(data[0][1])
                subject = _decode_subject(msg.get("Subject", ""))
                body = _get_body(msg)
                full_text = f"{subject}\n{body}"

                # Ищем сумму в тексте (например "500 ₽", "500.00", "500,00")
                price_patterns = [
                    rf"\b{SBP_PRICE}[\s,]*0*\s*[₽рубRUB]*\b",
                    rf"\b{SBP_PRICE}\.00\s*[₽руб]*\b",
                ]
                amount_found = any(re.search(p, full_text, re.IGNORECASE) for p in price_patterns)

                if amount_found:
                    # Ищем комментарий Pro {user_id}
                    match = re.search(r"Pro\s+(\d+)", full_text, re.IGNORECASE)
                    if match:
                        user_id = int(match.group(1))
                        # Проверяем, не обработан ли уже сегодня
                        if not db.payment_already_processed(user_id, SBP_PRICE):
                            found_users.append(user_id)
                            # Помечаем письмо как прочитанное
                            mail.store(num, "+FLAGS", "\\Seen")
            except Exception as e:
                print(f"Error processing email {num}: {e}")
                continue

        mail.close()
        mail.logout()
    except Exception as e:
        print(f"IMAP error: {e}")

    return found_users
