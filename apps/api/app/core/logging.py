"""PII masking for logs (and anything else that needs a masked string).

Every identifier is masked *before* a log record is written, so raw GSTINs,
Udyam numbers, phone numbers and ID numbers never reach log files or the LLM.
"""

import logging
import re

# 27ABCDE1234F1Z5 -> 27XXXXX1234F1Z5 (state code + tail kept, PAN letters hidden)
_GSTIN = re.compile(r"\b(\d{2})[A-Z]{5}(\d{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b")
# UDYAM-KL-00-3078801 -> UDYAM-KL-00-XXXX801
_UDYAM = re.compile(r"\b(UDYAM-[A-Z]{2}-\d{2}-)\d{4}(\d{3})\b")
# 12-digit Aadhaar-like numbers (optionally spaced) -> XXXX XXXX 1234
_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?(\d{4})\b")
# PAN ABCDE1234F -> XXXXX1234X
_PAN = re.compile(r"\b[A-Z]{5}(\d{4})[A-Z]\b")
# Indian mobile numbers, optional +91 -> XXXXXX1234
_PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{5}(\d{4})(?!\d)")


def mask_pii(text: str) -> str:
    text = _GSTIN.sub(r"\1XXXXX\2", text)
    text = _UDYAM.sub(r"\1XXXX\2", text)
    text = _AADHAAR.sub(r"XXXX XXXX \1", text)
    text = _PAN.sub(r"XXXXX\1X", text)
    text = _PHONE.sub(r"XXXXXX\1", text)
    return text


class PIIMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_pii(record.getMessage())
        record.args = None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(PIIMaskingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
