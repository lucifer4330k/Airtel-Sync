import logging
import sys

from app.core.logging import PIIMaskingFilter, configure_logging, mask_pii


def test_masks_gstin():
    assert mask_pii("gst 27ABCDE1234F1Z5 ok") == "gst 27XXXXX1234F1Z5 ok"


def test_masks_udyam():
    assert mask_pii("UDYAM-KL-00-3078801") == "UDYAM-KL-00-XXXX801"


def test_masks_phone_and_aadhaar():
    assert mask_pii("call +91 9876543210") == "call XXXXXX3210"
    assert mask_pii("aadhaar 1234 5678 9012") == "aadhaar XXXX XXXX 9012"


def test_masks_pan():
    assert mask_pii("PAN ABCDE1234F") == "PAN XXXXX1234X"


def test_leaves_normal_text_alone():
    text = "Clinic with 2 sites in Kochi wants 300 Mbps"
    assert mask_pii(text) == text


def test_filter_masks_formatted_args():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "lookup %s", ("27ABCDE1234F1Z5",), None)
    PIIMaskingFilter().filter(record)
    assert record.getMessage() == "lookup 27XXXXX1234F1Z5"


def test_masks_lowercase_identifiers():
    assert mask_pii("/gstin/27abcde1234f1z5") == "/gstin/27XXXXX1234f1z5"
    assert mask_pii("udyam-kl-00-3078801") == "udyam-kl-00-XXXX801"


def test_access_log_args_stay_a_tuple():
    # uvicorn.access unpacks (client, method, path, http_version, status) from args.
    args = ("127.0.0.1:5000", "GET", "/api/v1/mock/gstin/32TTNXB7384T1ZW", "1.1", 200)
    fmt = '%s - "%s %s HTTP/%s" %d'
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, fmt, args, None)
    PIIMaskingFilter().filter(record)
    client, method, path, version, status = record.args
    assert path == "/api/v1/mock/gstin/32XXXXX7384T1ZW"
    assert status == 200
    assert "32TTNXB" not in record.getMessage()


def test_masks_traceback_text():
    try:
        raise ValueError("bad gstin 27ABCDE1234F1Z5")
    except ValueError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    PIIMaskingFilter().filter(record)
    out = logging.Formatter().format(record)
    assert "27ABCDE" not in out
    assert "27XXXXX1234F1Z5" in out


def test_masks_non_string_messages():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, ValueError("27ABCDE1234F1Z5"), None, None)
    PIIMaskingFilter().filter(record)
    assert record.getMessage() == "27XXXXX1234F1Z5"


def test_configure_logging_covers_uvicorn_loggers():
    configure_logging()
    configure_logging()  # idempotent
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        filters = logging.getLogger(name).filters
        assert sum(isinstance(f, PIIMaskingFilter) for f in filters) == 1
