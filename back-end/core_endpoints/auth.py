"""
Authentication Endpoints - user registration, login, logout, and token verification

KEY CONCEPTS:
- ADMIN_SECRET: Pre-shared secret used ONLY during registration to grant initial admin privileges.
  Once registered, admin status is managed by existing admins in admin.py.
  Returned password is generated (12+ chars with mixed case, digits, symbols) and sent to user once.
- Token Verification: check_token() is a FastAPI dependency that validates JWT tokens.
  Two-level verification: (1) JWT decode with role claim, (2) database query to confirm active session.
  Returns user data (username, user_id, role) for use in protected endpoints.

Functions:
- generate_password(): Creates random secure password for new registrations.
- register(): Create new user account. Admin privileges require correct ADMIN_SECRET.
- login(): Authenticate user, generate JWT token with role claim, create session record.
- logout(): Revoke user session token, marking it as inactive.
- check_token(): FastAPI dependency for token validation (JWT + database status check).

Database Operations:
- Passwords are hashed with bcrypt before storage (pwd_context)
- Tokens stored in login_sessions table for revocation tracking
- JWT tokens include role claim for fast authorization checks
- Token revocation prevents replay attacks even after JWT expiration time
"""

import secrets
import sqlite3
import string
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from config import ADMIN_SECRET, SECRET_KEY, pwd_context
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from models import LoginRequest, LogoutRequest, RegisterRequest
from services.database import (
    check_session_status,
    db_cursor,
    get_user_by_id,
    insert_session,
    insert_user,
    purge_expired_sessions,
    revoke_session,
    select_password,
    select_user,
)

security = HTTPBearer()

# In-memory login throttle: max failures per (ip, username) within a window.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
_login_failures: dict[str, deque] = defaultdict(deque)


def _login_key(request: Request, username: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{username}"


def _too_many_attempts(key: str) -> bool:
    now = time.time()
    attempts = _login_failures[key]
    while attempts and now - attempts[0] > LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def _record_failure(key: str) -> None:
    _login_failures[key].append(time.time())


def _clear_failures(key: str) -> None:
    _login_failures.pop(key, None)


def generate_password(length: int = 12) -> str:
    """
    Generate a random secure password with mixed character types.

    Args:
        length (int): Password length in characters. Defaults to 12.

    Returns:
        str: Random password containing lowercase, uppercase, digits, and special characters.

    Note:
        Used during user registration to create an initial password.
        Password includes: a-z, A-Z, 0-9, !@#$%^&*-_+=?
    """
    characters = (
        string.ascii_lowercase
        + string.ascii_uppercase
        + string.digits
        + "!@#$%^&*-_+=?"
    )

    password = "".join(secrets.choice(characters) for _ in range(length))
    return password


def register(user: RegisterRequest) -> dict:
    """
    Register a new user account in the system.

    Args:
        user (RegisterRequest): Registration request containing full_name, username, is_admin flag, and optional admin_secret.

    Returns:
        dict: Contains username, generated password, admin status, and success message.

    Raises:
        HTTPException(403): If admin privileges requested but admin_secret is invalid.
        HTTPException(400): If username already exists (duplicate).

    Process:
        1. Validate admin_secret if admin privileges requested
        2. Generate random 12-character password (mixed case, digits, symbols)
        3. Hash password using bcrypt
        4. Insert new record into users table
        5. Return credentials to caller (password shown only once)
    """
    # Validate admin secret if user requests admin privileges
    is_admin = False
    if user.is_admin:
        if not ADMIN_SECRET or user.admin_secret != ADMIN_SECRET:
            raise HTTPException(status_code=403, detail="Invalid admin secret")
        is_admin = True

    generated_password = generate_password(12)
    hashed_password = pwd_context.hash(generated_password)

    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                insert_user, (user.full_name, user.username, hashed_password, is_admin)
            )
            return {
                "message": "User registered successfully",
                "username": user.username,
                "password": generated_password,
                "is_admin": is_admin,
            }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists") from None


def login(user: LoginRequest, request: Request) -> dict:
    """
    Authenticate user and generate JWT access token.

    Args:
        user (LoginRequest): Login request containing username and password.
        request (Request): Incoming request (used for throttling by client IP).

    Returns:
        dict: Contains access_token (JWT) and role ("admin" or "user").

    Raises:
        HTTPException(401): If username not found or password verification fails.
        HTTPException(429): If too many failed attempts were made recently.

    Process:
        1. Check the login throttle for this client/username
        2. Look up user by username
        3. Verify provided password against bcrypt hash
        4. Generate JWT token and store it in login_sessions
        5. Return token and role to client

    Security:
        - Password never exposed in responses or logs
        - Token expires in 24 hours
        - Repeated failures are throttled to slow brute force
    """
    key = _login_key(request, user.username)
    if _too_many_attempts(key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )

    # Opportunistically drop expired sessions so the table does not grow forever.
    purge_expired_sessions()

    with db_cursor(commit=True) as cursor:
        cursor.execute(select_password, (user.username,))
        result = cursor.fetchone()

        if not result:
            _record_failure(key)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        hashed_password = result[0]

        if not pwd_context.verify(user.password, hashed_password):
            _record_failure(key)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        _clear_failures(key)

        cursor.execute(select_user, (user.username,))
        user_id, _, _, is_admin = cursor.fetchone()

        # Generate token with role claim included
        token = jwt.encode(
            {
                "sub": user.username,
                "user_id": user_id,
                "role": "admin" if is_admin else "user",
                "jti": str(uuid.uuid4()),
                "exp": datetime.now(UTC) + timedelta(hours=24),
            },
            SECRET_KEY,
        )

        cursor.execute(insert_session, (token, user_id))

        return {"access_token": token, "role": "admin" if is_admin else "user"}


def logout(logout_request: LogoutRequest) -> dict:
    """
    Revoke user session token (logout).

    Args:
        logout_request (LogoutRequest): Logout request containing the token to revoke.

    Returns:
        dict: Success message confirming logout.

    Raises:
        HTTPException(400): If token is invalid, non-existent, or already revoked.

    Process:
        1. Look up token in login_sessions table
        2. Check current status (active or revoked)
        3. If valid and active, update status to 'revoked' in database
        4. Return success message

    Security:
        - Revoked tokens cannot be re-used for authentication
        - Token status checked in database (not just JWT expiration)
        - Prevents token replay attacks after logout
    """
    token = logout_request.token

    with db_cursor(commit=True) as cursor:
        cursor.execute(check_session_status, (token,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=400, detail="Invalid or non-existent token")

        if result[0] == "revoked":
            raise HTTPException(status_code=400, detail="Token already revoked")

        cursor.execute(revoke_session, (token,))

        return {"message": "Logged out successfully"}


def decode_and_validate_session(token: str) -> dict:
    """
    Decode a JWT and confirm its session is still active in the database.

    Refreshes the ``role`` claim from the database on every call so that
    role changes (e.g. demotion) take effect without waiting for token expiry.

    Raises:
        HTTPException(401): If the token is expired, malformed, unknown, or revoked.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Token expired. Please log in again."
        ) from None
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    with db_cursor() as cursor:
        cursor.execute(check_session_status, (token,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(
                status_code=401, detail="Invalid token. Please log in again."
            )

        if result[0] != "active":
            raise HTTPException(
                status_code=401, detail="Token has been revoked. Please log in again."
            )

        # Re-derive the role from the database, not the (possibly stale) token claim.
        user_id = payload.get("user_id")
        if user_id is not None:
            cursor.execute(get_user_by_id, (user_id,))
            row = cursor.fetchone()
            if row is not None:
                payload["role"] = "admin" if row[3] else "user"

    payload["token"] = token
    return payload


def check_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    FastAPI dependency: validate the Bearer token and return its user payload.

    Returns:
        dict: User data including username, user_id, role, and token.

    Raises:
        HTTPException(401): If token expired, invalid, malformed, or revoked.
    """
    return decode_and_validate_session(credentials.credentials)


def require_admin(user_data: dict = Depends(check_token)) -> dict:
    """
    FastAPI dependency: require an authenticated user with the admin role.

    Raises:
        HTTPException(403): If the authenticated user is not an admin.
    """
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_data
