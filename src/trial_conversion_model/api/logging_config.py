import json
import logging
from datetime import UTC, datetime
from pathlib import Path

LOG_PATH = Path("logs/predictions.jsonl")

# Attributes every LogRecord has; anything else came in via `extra={...}`.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonlFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(
            {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        )
        return json.dumps(entry, default=str)


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Only prediction events go to the JSONL file
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(JsonlFormatter())
    logging.getLogger("prediction").addHandler(file_handler)
