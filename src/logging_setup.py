import logging
import os
import sys
import time
from typing import Optional


def setup_logging(log_dir: Optional[str] = None) -> None:
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # UTC в логах
    class UtcFormatter(logging.Formatter):
        converter = time.gmtime

    fmt = UtcFormatter("%(asctime)s | %(levelname)s | %(message)s")

    # Консоль
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    # Файл (ежедневный не нужен, простой файл)
    handlers = [stream_handler]
    if log_dir:
        file_path = os.path.join(log_dir, "run.log")
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        handlers.append(file_handler)

    logger.handlers = handlers

