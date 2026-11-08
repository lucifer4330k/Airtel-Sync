"""KYC answer key: one test per applicant K01-K12 (see app/services/kyc/answer_key.py
and docs/kyc-answer-key.md). Runs the full pipeline: OCR -> field extraction ->
per-document checks -> cross-document checks -> verdict."""

import pytest

from app.services.kyc.answer_key import ANSWER_KEY, EXTRA_REASONS, evaluate


@pytest.mark.parametrize("applicant", sorted(ANSWER_KEY))
def test_answer_key(applicant):
    expected, phrase, _ = ANSWER_KEY[applicant]
    result, reasons = evaluate(applicant)
    assert result == expected, f"{applicant}: got {result} {reasons}"
    if phrase:
        assert any(phrase in r for r in reasons), f"{applicant}: '{phrase}' not in {reasons}"
    if applicant in EXTRA_REASONS:
        assert any(EXTRA_REASONS[applicant] in r for r in reasons), reasons


def test_every_planted_problem_is_caught():
    flagged = {a for a in ANSWER_KEY if evaluate(a)[0] != "pass"}
    assert flagged == {a for a, (v, _, _) in ANSWER_KEY.items() if v != "pass"}
