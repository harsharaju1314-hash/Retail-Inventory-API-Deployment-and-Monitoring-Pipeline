import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Format log records as single-line structured JSON objects for ingestion
    by CloudWatch Agent or centralized log aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Contextual metadata passed via extra={} or attached to record
        optional_fields = [
            "request_id",
            "method",
            "path",
            "status_code",
            "remote_addr",
            "duration_ms",
            "error_type",
            "error_details",
        ]
        for field in optional_fields:
            if hasattr(record, field):
                log_payload[field] = getattr(record, field)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logging(app=None) -> logging.Logger:
    """
    Configure application and root loggers with JSON formatting.
    Logs to stdout (for Docker / container engine) and optionally
    to a designated file path (for CloudWatch agent file collection).
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    formatter = JSONFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate output
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # StreamHandler writes JSON to stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)
    root_logger.addHandler(stream_handler)

    # Optional FileHandler if LOG_FILE_PATH is set
    log_file_path = os.getenv("LOG_FILE_PATH")
    if log_file_path:
        try:
            log_dir = os.path.dirname(os.path.abspath(log_file_path))
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
        except OSError as e:
            root_logger.warning(
                f"Failed to initialize file logger at {log_file_path}: {e}"
            )

    # Align Flask logger with root logger
    if app is not None:
        app.logger.handlers = root_logger.handlers
        app.logger.setLevel(log_level)

    return root_logger
