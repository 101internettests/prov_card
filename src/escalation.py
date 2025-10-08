import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class UrlStatus:
    consecutive_failures: int
    first_failure_ts: Optional[str]
    last_check_ts: Optional[str]


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def load_stats(path: str) -> Dict[str, UrlStatus]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
    except Exception:
        return {}
    stats: Dict[str, UrlStatus] = {}
    for url, data in raw.items():
        stats[url] = UrlStatus(
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            first_failure_ts=data.get("first_failure_ts"),
            last_check_ts=data.get("last_check_ts"),
        )
    return stats


def save_stats(path: str, stats: Dict[str, UrlStatus]) -> None:
    _ensure_dir(path)
    raw = {
        url: {
            "consecutive_failures": st.consecutive_failures,
            "first_failure_ts": st.first_failure_ts,
            "last_check_ts": st.last_check_ts,
        }
        for url, st in stats.items()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def should_alert_for_failure(count: int) -> bool:
    # Схема: 1-й, 4-й, 12-й прогон, далее каждые 10-й (20, 30, 40, ...)
    if count in (1, 4, 12):
        return True
    if count >= 20 and count % 10 == 0:
        return True
    return False


def update_status_for_check(stats_path: str, url: str, is_failure: bool) -> bool:
    """
    Обновляет статус URL с учётом результата прогона и возвращает, нужно ли отправлять алерт.
    """
    stats = load_stats(stats_path)
    current = stats.get(url, UrlStatus(consecutive_failures=0, first_failure_ts=None, last_check_ts=None))

    current.last_check_ts = _now_utc_str()

    if is_failure:
        if current.consecutive_failures == 0:
            current.first_failure_ts = current.last_check_ts
        current.consecutive_failures += 1
        alert_now = should_alert_for_failure(current.consecutive_failures)
    else:
        # Восстановление — сброс счётчика и отметка времени
        current.consecutive_failures = 0
        current.first_failure_ts = None
        alert_now = False

    stats[url] = current
    save_stats(stats_path, stats)
    return alert_now


def get_consecutive_failures(stats_path: str, url: str) -> int:
    """Возвращает текущее количество подряд идущих неуспешных прогонов по URL."""
    stats = load_stats(stats_path)
    current = stats.get(url)
    return int(current.consecutive_failures) if current else 0