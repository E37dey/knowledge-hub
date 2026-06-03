"""FastAPI dependencies for auth.

Every protected endpoint declares `Depends(get_current_user)`. A
missing / malformed / expired / forged token raises 401 with the
generic "Could not validate credentials" message and the RFC-prescribed
WWW-Authenticate: Bearer header.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models import User

# tokenUrl is for OpenAPI docs only — at runtime, OAuth2PasswordBearer
# just reads the Authorization header and strips the "Bearer " prefix.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT in the Authorization header to a User row.

    Any failure — missing/invalid token, missing subject, deleted user
    — yields the SAME 401, so callers can't distinguish "token bad"
    from "user gone".
    """
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    sub = payload.get("sub")
    if not sub:
        raise _CREDENTIALS_EXCEPTION

    try:
        user_id = UUID(sub)
    except ValueError:
        raise _CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _CREDENTIALS_EXCEPTION
    return user
