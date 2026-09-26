"""The bounded questions the orchestrator asks System 1 (and, if unsure, the LLM)."""

from orchestrator.ports import Question

BALANCE, TRANSACTIONS, LOST_CARD, AGENT, OTHER = (
    "balance",
    "transactions",
    "lost_card",
    "agent",
    "other",
)
NEEDS_AUTH = frozenset({BALANCE, TRANSACTIONS, LOST_CARD})


def intent(threshold: float) -> Question:
    return Question(
        name="intent",
        instructions="What does the bank customer want?",
        options={
            BALANCE: "their account balance or how much money they have",
            TRANSACTIONS: "a charge, payment, debit or transaction, including one they"
            " don't recognise, or their recent transactions",
            LOST_CARD: "their card is lost or stolen, or they want to block or freeze a card",
            AGENT: "to speak to a human agent or representative",
            OTHER: "a greeting, a general banking question, or anything else",
        },
        threshold=threshold,
    )


CONFIRM, DECLINE = "confirm", "decline"


def confirmation(threshold: float, action: str) -> Question:
    return Question(
        name="confirmation",
        instructions=f"The customer was asked to confirm: {action}. What did they answer?",
        options={
            CONFIRM: "clearly agrees and wants it done now",
            DECLINE: "refuses, hesitates, is unsure, or talks about something else",
        },
        threshold=threshold,
    )


def card_choice(threshold: float, cards: dict[str, str]) -> Question:
    """cards: card_id -> description, e.g. 'Visa debit card ending 4821'."""
    return Question(
        name="card",
        instructions="Which of these cards is the customer talking about?",
        options=cards,
        threshold=threshold,
    )
