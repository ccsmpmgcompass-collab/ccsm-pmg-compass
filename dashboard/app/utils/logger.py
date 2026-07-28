import logging
import logging.handlers
import os
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def get_logger(module_name: str) -> logging.Logger:
    name = f"pmg_compass.{module_name}"
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(console)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        _LOG_DIR / "compass.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger
