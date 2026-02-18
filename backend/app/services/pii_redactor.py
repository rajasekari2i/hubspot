"""PII redactor - Regex-based redaction before LLM transmission."""

import re

import structlog

logger = structlog.get_logger()

# Phone numbers: various formats (US, international)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[-.\s]?)?"
    r"(?:\(?\d{3}\)?[-.\s]?)"
    r"\d{3}[-.\s]?\d{4}"
    r"(?!\d)"
)

# SSN: xxx-xx-xxxx
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Credit card: 13-19 digit numbers with optional separators
_CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Email signature block: lines starting with common signature markers
_SIGNATURE_MARKERS = [
    r"^--\s*$",
    r"^Sent from my ",
    r"^Get Outlook for ",
    r"^_{3,}",
    r"^Best regards,",
    r"^Kind regards,",
    r"^Regards,",
    r"^Thanks,",
    r"^Thank you,",
    r"^Cheers,",
    r"^Sincerely,",
]
_SIGNATURE_PATTERN = re.compile(
    "|".join(_SIGNATURE_MARKERS), re.MULTILINE | re.IGNORECASE
)


def redact_pii(text: str) -> str:
    """Redact PII from email content before sending to LLM.

    Redacts:
        - Phone numbers -> [PHONE]
        - SSN patterns -> [REDACTED]
        - Credit card patterns -> [REDACTED]
        - Email signatures (stripped entirely)

    Retains:
        - Email addresses (needed for contact resolution)
        - Names (needed for context)
    """
    # Strip email signature first
    text = _strip_signature(text)

    # Redact SSN before phone (SSN pattern is more specific)
    text = _SSN_PATTERN.sub("[REDACTED]", text)

    # Redact credit card numbers
    text = _CC_PATTERN.sub("[REDACTED]", text)

    # Redact phone numbers
    text = _PHONE_PATTERN.sub("[PHONE]", text)

    return text


def _strip_signature(text: str) -> str:
    """Remove email signature block from text."""
    match = _SIGNATURE_PATTERN.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text
