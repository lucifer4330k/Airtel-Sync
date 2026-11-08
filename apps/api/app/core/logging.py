"""PII masking for logs (and anything else that needs a masked string).

Every identifier is masked *before* a log record is written, so raw GSTINs,
Udyam numbers, phone numbers and ID numbers never reach log files or the LLM.
"""

import logging
import re
from collections.abc import Mapping

# Case-insensitive: identifiers arrive lowercased in URLs and free text too.
# Over-masking a look-alike word is acceptable; leaking an ID is not.
_I = re.IGNORECASE
# 27ABCDE1234F1Z5 -> 27XXXXX1234F1Z5 (state code + tail kept, PAN letters hidden)
_GSTIN = re.compile(r"\b(\d{2})[A-Z]{5}(\d{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b", _I)
# UDYAM-KL-00-3078801 -> UDYAM-KL-00-XXXX801
_UDYAM = re.compile(r"\b(UDYAM-[A-Z]{2}-\d{2}-)\d{4}(\d{3})\b", _I)
# 12-digit Aadhaar-like numbers (optionally spaced) -> XXXX XXXX 1234
_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?(\d{4})\b")
# PAN ABCDE1234F -> XXXXX1234X
_PAN = re.compile(r"\b[A-Z]{5}(\d{4})[A-Z]\b", _I)
# Indian mobile numbers, optional +91 -> XXXXXX1234
_PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{5}(\d{4})(?!\d)")


def mask_pii(text: str) -> str:
    text = _TOKEN_PARAM.sub(r"\1[redacted]", text) if "=" in text else text
    text = _GSTIN.sub(r"\1XXXXX\2", text)
    text = _UDYAM.sub(r"\1XXXX\2", text)
    text = _AADHAAR.sub(r"XXXX XXXX \1", text)
    text = _PAN.sub(r"XXXXX\1X", text)
    text = _PHONE.sub(r"XXXXXX\1", text)
    return text


def _mask_arg(value):
    if isinstance(value, str):
        return mask_pii(value)
    # A bare int can still be a phone/Aadhaar number; only swap it if it masks.
    masked = mask_pii(str(value))
    return value if masked == str(value) else masked


# Owner capability tokens inside links: /track/12?t=<id>.<sig>, /resume?b=..&t=..
_TOKEN_PARAM = re.compile(r"([?&](?:t|share)=)[^&\s]+")


def redact_tokens(text: str) -> str:
    """Strip capability tokens from links before text is stored or shown to staff."""
    return _TOKEN_PARAM.sub(r"\1[redacted]", text)


class PIIMaskingFilter(logging.Filter):
    """Masks msg, each arg, traceback and stack text in place.

    Args are masked one by one rather than collapsed into msg, because some
    formatters (uvicorn's access log) unpack record.args positionally.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)
        elif record.msg is not None:
            # Exceptions, dicts etc. passed straight to logger.info(obj)
            record.msg = mask_pii(str(record.msg))
        if isinstance(record.args, Mapping):
            record.args = {k: _mask_arg(v) for k, v in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(_mask_arg(a) for a in record.args)
        if record.exc_info and not record.exc_text:
            # Formatters reuse exc_text when set, so the raw traceback never prints.
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = mask_pii(record.exc_text)
        if record.stack_info:
            record.stack_info = mask_pii(record.stack_info)
        return True


class MaskingFormatter(logging.Formatter):
    """Last line of defence: masks the fully formatted line, catching PII that
    only appears once msg and args are combined."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_pii(super().format(record))


# Uvicorn's loggers set propagate=False and log request paths such as
# /mock/gstin/{gstin}, so the root handler alone never sees them.
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi")


def configure_logging(level: int = logging.INFO) -> None:
    mask = PIIMaskingFilter()
    handler = logging.StreamHandler()
    handler.addFilter(mask)
    handler.setFormatter(MaskingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in _SERVER_LOGGERS:
        logger = logging.getLogger(name)
        # Logger-level filter covers records logged directly on it, even if the
        # server adds handlers later; handler-level covers child loggers.
        for target in (logger, *logger.handlers):
            if not any(isinstance(f, PIIMaskingFilter) for f in target.filters):
                target.addFilter(mask)
