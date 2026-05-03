"""Phone number normalization utilities."""

import re
from typing import Optional

PHONE_REGEX = r"^\+7\d{10}$"


def normalize_phone(v: Optional[str]) -> Optional[str]:
    """Normalize a Russian phone number to +7XXXXXXXXXX format."""
    if v is None:
        return v
    digits = "".join(ch for ch in v if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        normalized = "+7" + digits[1:]
    elif len(digits) == 10:
        normalized = "+7" + digits
    elif len(digits) == 11 and digits.startswith("7"):
        normalized = "+" + digits
    else:
        normalized = v.strip()
    if not re.match(PHONE_REGEX, normalized):
        return None
    return normalized
