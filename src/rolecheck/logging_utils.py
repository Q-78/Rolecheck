"""Logging configuration for repository initialization and future experiments."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from rolecheck.config import LoggingConfig


class JsonLineFormatter(logging.Formatter):
    """Minimal JSON-lines formatter without third-party logging dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(config: LoggingConfig, log_dir: str | Path | None = None) -> None:
    """Configure console logging and an optional file handler."""

    level = getattr(logging, config.level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"invalid logging level: {config.level}")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter: logging.Formatter
    formatter = (
        JsonLineFormatter()
        if config.json_lines
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_dir is not None:
        target_dir = Path(log_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(target_dir / config.filename, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
