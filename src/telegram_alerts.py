import logging
from typing import Optional

import requests


def send_telegram_alert(enabled: bool, bot_token: Optional[str], chat_id: Optional[str], message: str) -> bool:
    if not enabled:
        logging.info("Алерты отключены, сообщение не отправлено")
        return False
    if not bot_token or not chat_id:
        logging.warning("Не настроены BOT_TOKEN/CHAT_ID, алерт пропущен")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.ok:
            logging.info("Сообщение отправлено в Telegram")
            return True
        logging.error("Ошибка отправки в Telegram: %s", response.text)
        return False
    except requests.RequestException as exc:
        logging.exception("Исключение при отправке в Telegram: %s", exc)
        return False
