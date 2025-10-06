import argparse
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.config import load_config
from src.logging_setup import setup_logging
from src.selenium_checker import check_url_for_missing_fee
from src.sheets_appender import append_negative_result, get_sheet_url
from src.telegram_alerts import send_telegram_alert
from src.url_source import load_groups


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка наличия поля 'Абонентская плата' в карточках провайдеров")
    parser.add_argument("--group", help="Имя группы (лист Excel или имя файла без .txt)", default=None)
    args = parser.parse_args()

    config = load_config()
    setup_logging(config.log_dir)

    try:
        groups = load_groups(config.urls_dir)
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return 2

    if not groups:
        logging.error("Не найдено ни одной группы URL")
        return 2

    if args.group:
        if args.group not in groups:
            logging.error("Группа '%s' не найдена. Доступные: %s", args.group, ", ".join(sorted(groups.keys())))
            return 2
        selected = {args.group: groups[args.group]}
    else:
        selected = groups

    any_failures = False
    for group_name, urls in selected.items():
        logging.info("Группа: %s (кол-во URL: %d)", group_name, len(urls))
        for url in urls:
            missing, total, checked = check_url_for_missing_fee(
                url=url,
                headless=config.headless,
                wait_seconds=config.wait_timeout_seconds,
            )
            if missing:
                any_failures = True
                logging.warning("URL: %s | карточек: %d, проверено: %d, без абонплаты: %s", url, total, checked, ", ".join(missing))

                append_negative_result(
                    sheet_id=config.sheet_id,
                    service_account_json=config.google_service_account_json,
                    worksheet_title=config.sheet_worksheet_title,
                    url=url,
                    when_utc=datetime.now(timezone.utc),
                    providers_without_fee=missing,
                )

                parsed = urlparse(url)
                domain = parsed.netloc
                sheet_url = get_sheet_url(config.sheet_id) or ""
                message = (
                    "Пропало поле «Абонентская плата»\n"
                    f"Сайт: {domain}\n"
                    f"Ссылка на отчёт: {sheet_url}"
                )
                send_telegram_alert(
                    enabled=config.alerts_enabled,
                    bot_token=config.bot_token,
                    chat_id=config.chat_id,
                    message=message,
                )
            else:
                logging.info("URL: %s | карточек: %d, проверено: %d, все ок", url, total, checked)

    if not any_failures and config.success_alerts_enabled:
        groups_list = ", ".join(sorted(selected.keys()))
        send_telegram_alert(
            enabled=True,  # успехи отправляем только если глобально включено SUCCESS_ALERTS_ENABLED
            bot_token=config.bot_token,
            chat_id=config.chat_id,
            message=(
                "Проверка прошла успешно\n"
                f"Группы: {groups_list}"
            ),
        )

    return 1 if any_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
