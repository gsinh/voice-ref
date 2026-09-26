"""Turn what a caller *says* into the digits they meant.

Speech-to-text writes a spoken code in many ways: "123456", "1 2 3 4 5 6",
"one two three four five six", "one-two-three, four five six", "double five",
"triple zero", or "oh" for zero. The one-time code check must accept all of them.
"""

import re

_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "nought": "0",
    "one": "1", "two": "2", "to": "2", "too": "2", "three": "3", "four": "4", "for": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}  # fmt: skip
_REPEAT = {"double": 2, "triple": 3}


def spoken_digits(text: str) -> str:
    """All digits in the utterance, in order, with number words and repeats expanded."""
    out: list[str] = []
    repeat = 1
    for token in re.findall(r"[a-z]+|\d", text.lower()):
        if token in _REPEAT:
            repeat = _REPEAT[token]
            continue
        digit = token if token.isdigit() else _WORDS.get(token)
        if digit is not None:
            out.append(digit * repeat)
        repeat = 1
    return "".join(out)
