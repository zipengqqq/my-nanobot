from __future__ import annotations

import logging
from pathlib import Path


LOGGER_NAME = "my_agent.app"
LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "my_nanobot.log"


def _create_logger(log_file: Path | None = None) -> logging.Logger:
    """为 CLI 入口初始化文件日志。"""

    logger = logging.getLogger(LOGGER_NAME)
    resolved_log_file = (log_file or LOG_FILE_PATH).resolve()
    current_log_file = getattr(logger, "_my_agent_log_file", None)

    if logger.handlers and current_log_file == resolved_log_file:
        return logger

    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = logging.FileHandler(resolved_log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger._my_agent_log_file = resolved_log_file
    return logger

logger = _create_logger()
