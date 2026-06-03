"""Authentication endpoints: register, login.

These are the only routes that touch plaintext passwords. Hash at
registration; verify-and-discard at login. No plaintext ever lands
in the database, in a log line, or in a response body.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import Token, UserLogin, UserPublic, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> User:
    """Create a new user with a bcrypt-hashed password.

    Returns the public user representation (no hashed_password).
    409 if the email is already taken.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Verify credentials and return a JWT access token.

    The error message is intentionally generic — failures from
    unknown-email and wrong-password look identical. Distinguishing
    them would give an attacker a user-enumeration oracle.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    return Token(
        access_token=create_access_token(subject=str(user.id)),
        token_type="bearer",
    )
