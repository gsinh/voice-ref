"""Signed tokens shared by the orchestrator (issuer) and the MCP server (verifier).

A *shared kernel*: the one contract two modules must agree on byte-for-byte, so it
lives in a tiny library both depend on rather than in either module (ADR-0015).

Two token types, both standard JWTs (HS256) so a gateway such as agentgateway can
validate them too (ADR-0017):

- **Session token**: "this conversation is authenticated as customer X". The MCP
  server derives the customer from it; tools never take a customer id from the LLM.
- **Confirmation token**: "customer X explicitly confirmed action A on target T".
  Short-lived and bound to one action and target. Its `jti` becomes the bank's
  idempotency key, so replaying it can never act twice (ADR-0006).
"""

import time
import uuid
from dataclasses import dataclass

import jwt

ISSUER = "voice-ref/orchestrator"
SESSION_AUDIENCE = "voice-ref/mcp:session"
CONFIRMATION_AUDIENCE = "voice-ref/mcp:confirmation"
MIN_KEY_BYTES = 32
_ALGORITHM = "HS256"


class TokenError(Exception):
    """The token is missing, malformed, expired, or not valid for this use."""


@dataclass(frozen=True)
class Session:
    customer_id: str


@dataclass(frozen=True)
class Confirmation:
    customer_id: str
    action: str
    target: str
    token_id: str


def _check_key(key: str) -> None:
    if len(key.encode()) < MIN_KEY_BYTES:
        raise ValueError(f"signing key must be at least {MIN_KEY_BYTES} bytes")


def issue_session(key: str, customer_id: str, ttl_s: int = 900) -> str:
    _check_key(key)
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": SESSION_AUDIENCE, "sub": customer_id, "iat": now}
    return jwt.encode({**claims, "exp": now + ttl_s}, key, algorithm=_ALGORITHM)


def verify_session(key: str, token: str) -> Session:
    claims = _decode(key, token, SESSION_AUDIENCE)
    return Session(customer_id=claims["sub"])


def issue_confirmation(
    key: str, customer_id: str, action: str, target: str, ttl_s: int = 120
) -> str:
    _check_key(key)
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CONFIRMATION_AUDIENCE,
        "sub": customer_id,
        "act": action,
        "tgt": target,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl_s,
    }
    return jwt.encode(claims, key, algorithm=_ALGORITHM)


def verify_confirmation(
    key: str, token: str, *, customer_id: str, action: str, target: str
) -> Confirmation:
    """Verify the token *and* that it authorises exactly this customer, action and target."""
    claims = _decode(key, token, CONFIRMATION_AUDIENCE)
    if (claims["sub"], claims.get("act"), claims.get("tgt")) != (customer_id, action, target):
        raise TokenError("confirmation does not match this customer, action and target")
    return Confirmation(customer_id, action, target, token_id=claims["jti"])


def _decode(key: str, token: str, audience: str) -> dict[str, str]:
    _check_key(key)
    try:
        claims: dict[str, str] = jwt.decode(
            token,
            key,
            algorithms=[_ALGORITHM],  # pinned: never accept "none" or a different algorithm
            audience=audience,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return claims
