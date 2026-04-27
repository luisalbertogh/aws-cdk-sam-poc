"""JSON structured logging configuration for the Chef UI application."""

import datetime
import json
import logging

# Fields that are built into every LogRecord — we exclude them from the "extra" dump
# to avoid noise in the structured output.
_BUILTIN_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Any keyword arguments passed via ``extra={}`` to a logging call are
    promoted to top-level fields in the JSON output.
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        record.message = record.getMessage()

        log_record: dict = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)

        # Promote any extra= fields to the top level
        for key, value in record.__dict__.items():
            if key not in _BUILTIN_LOG_RECORD_ATTRS and not key.startswith("_"):
                log_record[key] = value

        return json.dumps(log_record, default=str)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that emits JSON-structured output to stdout.

    Calling this multiple times with the same *name* is safe — handlers are
    only attached once.

    Args:
        name: Logger name, typically ``__name__``.
        level: Minimum log level (default ``INFO``).

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    return logger
