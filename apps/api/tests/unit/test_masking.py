import logging

from app.core.logging import PIIMaskingFilter, mask_pii


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
