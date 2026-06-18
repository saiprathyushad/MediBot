"""
auth.py — Authentication for MediBot.

Provides a hardcoded user store with the five demo accounts specified in the
assignment, and JWT-based token creation/verification using python-jose.
The JWT payload carries the username and role so that every /chat request
can identify who is asking and what they are allowed to access without a
database lookup.
"""

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# Secret key used to sign JWTs. Must be set in .env for production.
SECRET_KEY: str = os.getenv("SECRET_KEY", "medibot-dev-secret-change-in-production")
ALGORITHM: str = "HS256"
TOKEN_EXPIRE_HOURS: int = 8  # tokens expire after an 8-hour shift

# Hardcoded demo users — username → {password, role}.
# In a real system these would be hashed passwords in a database.
USERS: dict[str, dict] = {
    "dr.mehta":     {"password": "doctor",            "role": "doctor"},
    "nurse.priya":  {"password": "nurse",             "role": "nurse"},
    "billing.ravi": {"password": "billing_executive", "role": "billing_executive"},
    "tech.anand":   {"password": "technician",        "role": "technician"},
    "admin.sys":    {"password": "admin",             "role": "admin"},
}


def authenticate_user(username: str, password: str) -> dict | None:
    """
    Validate credentials against the user store.
    Returns the user record (with role) if valid, or None if not.
    """
    user = USERS.get(username)
    if user and user["password"] == password:
        return user
    return None


def create_token(username: str, role: str) -> str:
    """
    Create a signed JWT containing the username and role.
    The token expires after TOKEN_EXPIRE_HOURS so sessions are time-bounded.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Returns the payload dict if valid.
    Raises JWTError if the token is invalid, expired, or tampered with.
    The caller (FastAPI dependency) is responsible for converting this to
    an HTTP 401 response.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
