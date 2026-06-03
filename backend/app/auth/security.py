"""Password hashing + JWT creation/verification.

Sensitive — every helper here is a security primitive. Changes are
review-worthy. Hard rules:
  * Plaintext passwords NEVER leave this module — only hash and
    verify primitives are exposed.
  * JWTs are signed with SECRET_KEY from settings, never hardcoded.
  * Expiry is enforced on decode (jose raises on `exp` past now).

Implementation note: we use the `bcrypt` package directly rather than
going through passlib. Passlib's `CryptContext` is useful when
migrating between hash schemes in legacy systems; we have no such
problem, and recent passlib versions ship a compatibility shim
against bcrypt 4+ that crashes under Python 3.14. Dropping the
abstraction cuts a fragile dep without losing any feature we use.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings

# bcrypt's Blowfish core rejects inputs longer than 72 bytes. We
# truncate explicitly so a long-but-legal password can't crash the
# server; a 72-byte secret already carries ~430 bits of entropy when
# sampled uniformly, so the truncation has no practical cost.
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    """Encode the password as UTF-8 and clamp at bcrypt's input limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of `plain` as a utf-8 string.

    `bcrypt.gensalt()` uses the library default cost factor (12 rounds
    as of bcrypt 4.x). Higher cost = slower verify = harder offline
    cracking, at the price of online auth latency.
    """
    hashed = bcrypt.hashpw(_prepare(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time compare of `plain` against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except ValueError:
        # Stored hash is malformed (DB corruption, schema drift, etc.).
        # Treat as a failed verify rather than crash — defence in depth.
        return False


def create_access_token(subject: str) -> str:
    """Issue a signed JWT carrying `subject` (the user id as string).

    The token expires after ACCESS_TOKEN_EXPIRE_MINUTES from settings.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Decode + verify signature + check expiry.

    Raises `jose.JWTError` (and subclasses, e.g. ExpiredSignatureError)
    on any failure. Callers convert that to HTTP 401.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
