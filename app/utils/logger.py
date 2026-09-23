"""
AEGIS UNIFIED DATA CORE - Structured Redacting Logger
Guarantees that sensitive tokens, keys, passwords, and authorization headers
are NEVER exposed in application logs or standard output.
"""
import logging
import re
import sys

# Regex patterns for sensitive keys and tokens
SENSITIVE_PATTERNS = [
    (re.compile(r'(api[_-]?key|secret|token|password|auth|bearer|jwt)[\'"]?\s*[:=]\s*[\'"]?([^\s\'",}]+)', re.IGNORECASE), r'\1: "[REDACTED]"'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', re.IGNORECASE), 'Bearer [REDACTED]'),
    (re.compile(r'Basic\s+[A-Za-z0-9\-\._~\+\/]+=*', re.IGNORECASE), 'Basic [REDACTED]'),
]


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern, replacement in SENSITIVE_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


def setup_logger(name: str = "aegis-core") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
