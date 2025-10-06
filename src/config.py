from dataclasses import dataclass
from typing import Optional
import os
from dotenv import load_dotenv


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Config:
    urls_dir: str
    headless: bool
    alerts_enabled: bool
    success_alerts_enabled: bool
    bot_token: Optional[str]
    chat_id: Optional[str]
    sheet_id: Optional[str]
    google_service_account_json: Optional[str]
    sheet_worksheet_title: Optional[str]
    wait_timeout_seconds: int
    log_dir: str


def load_config() -> Config:
    load_dotenv()

    urls_dir = os.getenv("URLS_DIR", "data/urls")
    headless = _parse_bool(os.getenv("HEADLESS", "true"), True)
    alerts_enabled = _parse_bool(os.getenv("ALERTS_ENABLED", "true"), True)
    success_alerts_enabled = _parse_bool(os.getenv("SUCCESS_ALERTS_ENABLED", "false"), False)

    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    sheet_id = os.getenv("SHEET_ID")
    google_service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_worksheet_title = os.getenv("SHEET_WORKSHEET_TITLE")

    wait_timeout_seconds_str = os.getenv("WAIT_TIMEOUT_SECONDS", "15")
    try:
        wait_timeout_seconds = int(wait_timeout_seconds_str)
    except ValueError:
        wait_timeout_seconds = 15

    log_dir = os.getenv("LOG_DIR", "logs")

    return Config(
        urls_dir=urls_dir,
        headless=headless,
        alerts_enabled=alerts_enabled,
        success_alerts_enabled=success_alerts_enabled,
        bot_token=bot_token,
        chat_id=chat_id,
        sheet_id=sheet_id,
        google_service_account_json=google_service_account_json,
        sheet_worksheet_title=sheet_worksheet_title,
        wait_timeout_seconds=wait_timeout_seconds,
        log_dir=log_dir,
    )
