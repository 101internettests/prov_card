import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import os as _os
import sys as _sys
_ROOT = _os.path.dirname(_os.path.abspath(__file__))
_SRC = _os.path.join(_ROOT, "..", "src")
if _ROOT not in _sys.path:
    _sys.path.append(_ROOT)
if _SRC not in _sys.path:
    _sys.path.append(_SRC)

from src.config import load_config
from src.logging_setup import setup_logging
from src.selenium_checker import check_url_for_missing_fee
from src.sheets_appender import append_negative_result, get_sheet_url
from src.telegram_alerts import send_telegram_alert
from src.url_source import load_urls
from src.escalation import update_status_for_check


@pytest.mark.e2e
def test_provider_cards_abonent_fee():
    config = load_config()
    setup_logging(config.log_dir)

    urls = load_urls(config.urls_dir)
    assert urls, "Список URL пуст"

    any_failures = False
    failures_messages: list[str] = []

    for url in urls:
        missing, total, checked = check_url_for_missing_fee(
            url=url,
            headless=config.headless,
            wait_seconds=config.wait_timeout_seconds,
        )
        is_failure = bool(missing)
        if is_failure:
            any_failures = True
            failures_messages.append(
                f"URL: {url} | карточек: {total}, проверено: {checked}, без абонплаты: {', '.join(missing)}"
            )
            append_negative_result(
                sheet_id=config.sheet_id,
                service_account_json=config.google_service_account_json,
                worksheet_title=config.sheet_worksheet_title,
                url=url,
                when_utc=datetime.now(timezone.utc),
                providers_without_fee=missing,
            )
            should_alert = update_status_for_check(config.stats_file, url, is_failure=True)
            if should_alert:
                message = (
                    "Пропало поле «Абонентская плата»\n"
                    f"Страница: {url}\n"
                    f"Ссылка на отчёт: {get_sheet_url(config.sheet_id) or ''}"
                )
                send_telegram_alert(
                    enabled=config.alerts_enabled,
                    bot_token=config.bot_token,
                    chat_id=config.chat_id,
                    message=message,
                )
        else:
            update_status_for_check(config.stats_file, url, is_failure=False)

    if not any_failures and config.success_alerts_enabled:
        total_checked = len(urls)
        ts_msk = (
            datetime.now(timezone.utc)
            .astimezone(ZoneInfo("Europe/Moscow"))
            .strftime("%Y-%m-%d %H:%M:%S %Z")
        )
        send_telegram_alert(
            enabled=True,
            bot_token=config.bot_token,
            chat_id=config.chat_id,
            message=(
                "Проверка прошла успешно\n"
                f"Проверено URL: {total_checked}\n"
                f"Время проверки (МСК): {ts_msk}"
            ),
        )

    assert not any_failures, "\n" + "\n".join(failures_messages)
