import pytest

from orchestrator.spoken import spoken_digits


@pytest.mark.parametrize(
    "said",
    [
        "123456",
        "1 2 3 4 5 6",
        "123-456",
        "one two three four five six",
        "One, two, three... four five six.",
        "it's 1 2 3, four five six",
        "one two three for five six",  # STT homophone
    ],
)
def test_ways_of_saying_123456(said: str) -> None:
    assert spoken_digits(said) == "123456"


def test_repeats_and_zero() -> None:
    assert spoken_digits("double five oh triple nine") == "550999"
    assert spoken_digits("zero zero one") == "001"


def test_words_that_are_not_digits_are_ignored() -> None:
    assert spoken_digits("sure, the code is") == ""
