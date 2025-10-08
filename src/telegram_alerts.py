from typing import Optional
import logging
import requests


def send_telegram_alert(enabled: bool, bot_token: Optional[str], chat_id: Optional[str], message: str) -> None:
    if not enabled:
        return
    if not bot_token or not chat_id:
        logging.warning("Телеграм-алерт включён, но не задан BOT_TOKEN/CHAT_ID")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message})
        if resp.status_code >= 400:
            logging.error("Ошибка отправки в Telegram: %s %s", resp.status_code, resp.text)
    except Exception as exc:  # noqa: BLE001
        logging.error("Исключение при отправке в Telegram: %s", exc)


