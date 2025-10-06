import os
from datetime import datetime, timezone

import pytest

from src.config import load_config
from src.logging_setup import setup_logging
from src.selenium_checker import check_url_for_missing_fee
from src.sheets_appender import append_negative_result, get_sheet_url
from src.telegram_alerts import send_telegram_alert
from src.url_source import load_groups
from src.escalation import update_status_for_check


@pytest.mark.e2e
def test_provider_cards_abonent_fee():
    config = load_config()
    setup_logging(config.log_dir)

    groups = load_groups(config.urls_dir)
    assert groups, "Не найдено ни одной группы URL"

    only_group = os.getenv("TEST_GROUP")
    if only_group:
        assert only_group in groups, f"Группа '{only_group}' не найдена"
        groups = {only_group: groups[only_group]}

    any_failures = False
    failures_messages: list[str] = []

    for group_name, urls in groups.items():
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
                    f"[{group_name}] URL: {url} | карточек: {total}, проверено: {checked}, без абонплаты: {', '.join(missing)}"
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
        groups_list = ", ".join(sorted(groups.keys()))
        sheet_url = get_sheet_url(config.sheet_id) or ""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        send_telegram_alert(
            enabled=True,
            bot_token=config.bot_token,
            chat_id=config.chat_id,
            message=(
                "Проверка прошла успешно\n"
                f"Группы: {groups_list}\n"
                f"Ссылка на отчёт: {sheet_url}\n"
                f"Время проверки: {ts}"
            ),
        )

    assert not any_failures, "\n" + "\n".join(failures_messages)
