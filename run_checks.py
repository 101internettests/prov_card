import argparse
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import os as _os
import sys as _sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Гарантируем доступность корня и src/ для импорта
_ROOT = _os.path.dirname(_os.path.abspath(__file__))
_SRC = _os.path.join(_ROOT, "src")
if _ROOT not in _sys.path:
    _sys.path.append(_ROOT)
if _SRC not in _sys.path:
    _sys.path.append(_SRC)

from src.config import load_config
from src.logging_setup import setup_logging
from src.selenium_checker import check_url_with_driver, build_driver, check_url_for_missing_fee, PageOpenTimeout
from src.sheets_appender import append_negative_result, get_sheet_url
from src.telegram_alerts import send_telegram_alert
from src.url_source import load_urls
from src.escalation import update_status_for_check


def _check_url_parallel(url: str, cfg) -> tuple[str, list[str], int, int]:
    """Запуск проверки URL в отдельном драйвере (для parallel режима)."""
    driver = build_driver(
        headless=cfg.headless,
        wait_seconds=cfg.wait_timeout_seconds,
        page_load_strategy=cfg.page_load_strategy,
        disable_images=cfg.disable_images,
        disable_css=cfg.disable_css,
        disable_fonts=cfg.disable_fonts,
    )
    try:
        missing, total, checked = check_url_with_driver(
            driver=driver,
            url=url,
            wait_seconds=cfg.wait_timeout_seconds,
        )
        return url, missing, total, checked
    finally:
        driver.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка наличия поля 'Абонентская плата' в карточках провайдеров")
    parser.add_argument("--workers", type=int, default=1, help="Параллельных потоков на группу (>=1)")
    args = parser.parse_args()

    config = load_config()
    setup_logging(config.log_dir)

    try:
        urls = load_urls(config.urls_dir)
    except (FileNotFoundError, ValueError) as exc:
        logging.error(str(exc))
        return 2

    if not urls:
        logging.error("Список URL пуст")
        return 2

    any_failures = False
    sheet_url = get_sheet_url(config.sheet_id) or ""
    stats_lock = threading.Lock()

    logging.info("Кол-во URL: %d, workers=%d", len(urls), max(1, args.workers))
    timed_out_urls: list[str] = []

    if max(1, args.workers) == 1:
            # Последовательно: создаём и закрываем браузер для каждого URL, чтобы исключить зависание на финальном quit()
            for url in urls:
                try:
                    missing, total, checked = check_url_for_missing_fee(
                        url=url,
                        headless=config.headless,
                        wait_seconds=config.wait_timeout_seconds,
                    )
                    is_failure = bool(missing)
                    if is_failure:
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

                        with stats_lock:
                            should_alert = update_status_for_check(config.stats_file, url, is_failure=True)
                        if should_alert:
                            parsed = urlparse(url)
                            domain = parsed.netloc
                            message = (
                                "Пропало поле «Абонентская плата»\n"
                                f"Сайт: {domain}\n"
                                f"Страница: {url}\n"
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
                        with stats_lock:
                            update_status_for_check(config.stats_file, url, is_failure=False)
                except PageOpenTimeout as exc:
                    logging.info("URL пропущен из-за таймаута: %s", exc.url)
                    timed_out_urls.append(exc.url)
                    with stats_lock:
                        update_status_for_check(config.stats_file, url, is_failure=False)
                except Exception as exc:
                    any_failures = True
                    logging.exception("Ошибка при обработке URL (sequential): %s | %s", url, exc)
                    with stats_lock:
                        update_status_for_check(config.stats_file, url, is_failure=True)
    else:
        # Параллельно: каждый URL в своём драйвере, побочные эффекты в главном потоке
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_to_url = {
                executor.submit(_check_url_parallel, url, config): url for url in urls
            }
            # Жёсткий таймаут на получение результата одной задачи, чтобы пул не зависал навсегда
            per_future_timeout = max(1, config.wait_timeout_seconds) * 4
            for future in as_completed(future_to_url, timeout=None):
                url = future_to_url[future]
                try:
                    url, missing, total, checked = future.result(timeout=per_future_timeout)
                    is_failure = bool(missing)
                    if is_failure:
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

                        with stats_lock:
                            should_alert = update_status_for_check(config.stats_file, url, is_failure=True)
                        if should_alert:
                            parsed = urlparse(url)
                            domain = parsed.netloc
                            message = (
                                "Пропало поле «Абонентская плата»\n"
                                f"Сайт: {domain}\n"
                                f"Страница: {url}\n"
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
                        with stats_lock:
                            update_status_for_check(config.stats_file, url, is_failure=False)
                except PageOpenTimeout as exc:
                    logging.info("URL пропущен из-за таймаута: %s", exc.url)
                    timed_out_urls.append(exc.url)
                    with stats_lock:
                        update_status_for_check(config.stats_file, url, is_failure=False)
                except Exception as exc:
                    any_failures = True
                    logging.exception("Ошибка при обработке URL (parallel): %s | %s", url, exc)
                    with stats_lock:
                        update_status_for_check(config.stats_file, url, is_failure=True)

    if not any_failures and config.success_alerts_enabled:
        total_checked = len(urls)
        ts_msk = (
            datetime.now(timezone.utc)
            .astimezone(ZoneInfo("Europe/Moscow"))
            .strftime("%Y-%m-%d %H:%M:%S %Z")
        )
        success_msg = (
            "Проверка прошла успешно\n"
            f"Проверено URL: {total_checked}\n"
            f"Время проверки (МСК): {ts_msk}"
        )
        if timed_out_urls:
            success_msg += "\nНе открылись (по таймауту):\n" + "\n".join(timed_out_urls)
        send_telegram_alert(
            enabled=True,
            bot_token=config.bot_token,
            chat_id=config.chat_id,
            message=success_msg,
        )

    return 1 if any_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
