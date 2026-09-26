"""Turn bank data into text an LLM (and a TTS engine) can read without doing arithmetic.

Formatting money in code, not in the model, removes a whole class of hallucination:
the model repeats "₹82,450.00" instead of converting 8245000 paise itself.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def format_inr(paise: int) -> str:
    """Indian digit grouping: ₹1,56,320.50 (lakh/crore style), sign kept separate."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return f"{sign}₹{digits}.{p:02d}"


def format_when(ts: datetime) -> str:
    """e.g. 'Fri 25 Sep 2026, 21:13 IST'."""
    return ts.astimezone(IST).strftime("%a %d %b %Y, %H:%M IST")
