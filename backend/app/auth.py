"""Accounts for the voice game: passwords and sign-in tokens.

- Passwords are hashed with scrypt (Python's standard library), a slow,
  memory-hard hash made for passwords. Each one gets its own random salt, so
  equal passwords have different hashes. The plain password is never stored.
- After sign-up or sign-in the browser gets a signed token (a JWT) that says
  "user 7, valid until ...". Requests send it as `Authorization: Bearer <token>`
  (WebSockets, which can't send headers from a browser, pass it as `?token=`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from .db import get_session
from .models import User

# scrypt cost: 2**14 rounds, 16 MB of memory per hash. About 50 ms on a laptop.
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), dklen=32, **SCRYPT)
    return hmac.compare_digest(candidate, base64.b64decode(digest))  # constant time


def create_token(user_id: int, secret: str, days: float) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode({"sub": str(user_id), "exp": expires}, secret, algorithm="HS256")


def user_id_from_token(token: str, secret: str) -> int | None:
    try:
        return int(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


_bearer = HTTPBearer(auto_error=False)


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """FastAPI dependency: the signed-in user, or 401."""
    user_id = user_id_from_token(credentials.credentials, request.app.state.jwt_secret) if credentials else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Please sign in again.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]
