"""
Structured Logging Infrastructure for Mini-OSPF.
"""

import json
import logging
import sys
import time


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as JSON objects for structured observability."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "router_id"):
            payload["router_id"] = record.router_id
        if hasattr(record, "interface"):
            payload["interface"] = record.interface
        if hasattr(record, "neighbor"):
            payload["neighbor"] = record.neighbor
        if hasattr(record, "event"):
            payload["event"] = record.event
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO", log_format: str = "text", log_file: str | None = None) -> None:
    """Configure root logger with console and optional file handlers."""
    root = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        console_handler.setFormatter(StructuredJsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        console_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        if log_format.lower() == "json":
            file_handler.setFormatter(StructuredJsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        root.addHandler(file_handler)
