"""
Database Module - SQLite schema initialization and query helpers

This module manages all database operations for the application:
- User management (registration, authentication, admin status)
- Login session tracking (token revocation, session status)
- Chat session storage (conversation metadata)
- Chat message persistence (conversation history)

Database Structure:
- users: User accounts with hashed passwords and admin flags
- login_sessions: Active/revoked JWT tokens for auth security
- chat_sessions: Chat conversation containers (one per user session)
- chat_messages: Individual messages within conversations (user + assistant)

All tables use CASCADE DELETE for referential integrity.
Foreign keys enforce user ownership of sessions and messages.

Each operation opens its own short-lived connection so the app is safe under
FastAPI's thread pool (no connection shared across threads).
"""

import os
import sqlite3
from contextlib import contextmanager

os.makedirs("data", exist_ok=True)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/users.db")


def _connect() -> sqlite3.Connection:
    """Open a new connection with foreign keys enabled."""
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    # Foreign keys are OFF by default in SQLite; enable them for ON DELETE CASCADE.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_cursor(commit: bool = False):
    """Yield a cursor on a dedicated connection, committing and closing it."""
    connection = _connect()
    cursor = connection.cursor()
    try:
        yield cursor
        if commit:
            connection.commit()
    finally:
        cursor.close()
        connection.close()


def init_db():
    """
    Initialize database schema on application startup.
    Creates all tables if they don't exist.
    Performs migrations for existing databases (e.g., adding is_admin column).
    """
    with db_cursor(commit=True) as cursor:
        # Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        )
        """)

        # Migration: Add is_admin column if missing (for existing databases)
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if "is_admin" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

        # Login Sessions Table - tracks active/revoked JWT tokens
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_sessions (
            session_number INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Chat Sessions Table - represents a conversation container
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'New chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Chat Messages Table - individual messages within a session
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
        """)

        # Personas Table - assistant personalities (global, not per-user)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Seed default personas on first run
        cursor.execute("SELECT COUNT(*) FROM personas")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO personas (name, prompt) VALUES (?, ?)",
                [
                    (
                        "Expert Technique",
                        "Tu es un expert technique. Réponds avec précision et rigueur.",
                    ),
                    (
                        "Assistant Simplifié",
                        "Explique de manière simple et accessible, même pour les débutants.",
                    ),
                    (
                        "Expert Métier",
                        "Réponds avec une expertise métier approfondie et des références réglementaires.",
                    ),
                ],
            )

        # Purge login sessions older than the token lifetime (24h).
        cursor.execute(
            "DELETE FROM login_sessions WHERE created_at < datetime('now', '-1 day')"
        )


init_db()


# ──────────────────────────────────────────────────────────────────────────────
# USER QUERY CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
insert_user = (
    "INSERT INTO users (full_name, username, password, is_admin) VALUES (?, ?, ?, ?)"
)
select_user = "SELECT id, full_name, username, is_admin FROM users WHERE username=?"
select_password = "SELECT password FROM users WHERE username=?"
select_user_id = "SELECT id FROM users WHERE username=?"
get_user_by_id = "SELECT id, full_name, username, is_admin FROM users WHERE id=?"
get_all_users = "SELECT id, full_name, username, is_admin FROM users"
update_user_admin_status = "UPDATE users SET is_admin = ? WHERE id = ?"

# ──────────────────────────────────────────────────────────────────────────────
# LOGIN SESSION QUERY CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
insert_session = (
    "INSERT INTO login_sessions (token, status, user_id) VALUES (?, 'active', ?)"
)
revoke_session = "UPDATE login_sessions SET status = 'revoked' WHERE token = ?"
check_session_status = "SELECT status FROM login_sessions WHERE token = ?"


# ──────────────────────────────────────────────────────────────────────────────
# CHAT SESSION HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def create_chat_session(user_id: int, title: str = "New chat") -> int:
    """
    Create a new chat session for a user.

    Args:
        user_id (int): ID of the user creating the session.
        title (str): Initial session title. Defaults to "New chat".

    Returns:
        int: ID of the newly created session (lastrowid).

    Note:
        - Uses default title "New chat" until first message is sent
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO chat_sessions (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cursor.lastrowid


def get_chat_sessions(user_id: int) -> list:
    """
    Retrieve all chat sessions for a user, sorted by most recent first.

    Args:
        user_id (int): ID of the user whose sessions to retrieve.

    Returns:
        list[dict]: List of session objects with keys: id, title, created_at, updated_at.
                   Sorted by updated_at DESC (most recent conversations first).

    Use Case:
        Called to populate sidebar/conversation list in frontend.
    """
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        return [
            {"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in rows
        ]


def delete_chat_session(session_id: int, user_id: int) -> bool:
    """
    Delete a chat session and cascade-delete all its messages.

    Args:
        session_id (int): ID of the session to delete.
        user_id (int): ID of the user (ownership verification).

    Returns:
        bool: True if session was deleted, False if session not found or doesn't belong to user.

    Cascade Behavior:
        - Deletes session record from chat_sessions table
        - Database automatically deletes all related messages (ON DELETE CASCADE)

    Note:
        Verifies ownership: only deletes sessions that belong to the authenticated user.
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return cursor.rowcount > 0


def update_session_title(session_id: int, title: str) -> None:
    """
    Update the title of a chat session.

    Args:
        session_id (int): ID of the session to update.
        title (str): New title for the session.

    Note:
        Called by chat.py on first message to replace "New chat".
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )


def get_session_title(session_id: int) -> str:
    """
    Retrieve the current title of a chat session.

    Args:
        session_id (int): ID of the session.

    Returns:
        str: Current session title, or "New chat" if session not found.

    Note:
        Used to detect first message: if title is still "New chat", generate new title.
    """
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT title FROM chat_sessions WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else "New chat"


# ──────────────────────────────────────────────────────────────────────────────
# CHAT MESSAGE HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def save_message(session_id: int, role: str, content: str) -> None:
    """
    Save a message (user or assistant) to a chat session.

    Args:
        session_id (int): ID of the session to save message to.
        role (str): Message role: "user" or "assistant".
        content (str): Message text content.

    Side Effects:
        - Inserts message into chat_messages table
        - Updates parent session's updated_at timestamp to CURRENT_TIMESTAMP

    Note:
        Timestamp update ensures sessions sort by most recent activity.
    """
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def get_messages(session_id: int, limit: int = 10) -> list:
    """
    Retrieve recent messages from a chat session in chronological order.

    Args:
        session_id (int): ID of the session to retrieve messages from.
        limit (int): Maximum number of recent messages to return. Defaults to 10.
                    Typical use: 50 for context window (≈25 exchanges).

    Returns:
        list[dict]: Messages sorted oldest-to-newest with keys: role, content.
                   Example: [{"role": "user", "content": "Hello"}, ...]

    Context Window:
        The limit parameter prevents exceeding LLM context limits (Ollama window).
        Typical range: 10-50 messages depending on token budget.
        Recent messages included only; older messages discarded if limit exceeded.

    Note:
        - Messages retrieved in DESC order then reversed to be chronological
        - Used by chat.py to build RAG context for LLM
    """
    with db_cursor() as cursor:
        # Take the most recent `limit` messages by id, then return them oldest-first.
        cursor.execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (session_id, limit),
        )
        return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]


def session_belongs_to_user(session_id: int, user_id: int) -> bool:
    """
    Verify that a chat session belongs to a specific user (ownership check).

    Args:
        session_id (int): ID of the session to verify.
        user_id (int): ID of the user to check ownership against.

    Returns:
        bool: True if session exists and belongs to user, False otherwise.

    Security:
        Used by chat.py endpoints to enforce user isolation:
        - Only user can access their sessions
        - Prevents cross-user data leakage
        - All session operations require this verification

    Note:
        Critical for multi-tenant safety. Always called before allowing access.
    """
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return cursor.fetchone() is not None


# ──────────────────────────────────────────────────────────────────────────────
# PERSONA HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def list_personas() -> list:
    """Return all personas ordered by id."""
    with db_cursor() as cursor:
        cursor.execute("SELECT id, name, prompt FROM personas ORDER BY id")
        return [
            {"id": row[0], "name": row[1], "prompt": row[2]}
            for row in cursor.fetchall()
        ]


def create_persona(name: str, prompt: str) -> int:
    """Insert a persona and return its id."""
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO personas (name, prompt) VALUES (?, ?)",
            (name, prompt),
        )
        return cursor.lastrowid


def update_persona(persona_id: int, name: str, prompt: str) -> bool:
    """Update a persona; return True if it existed."""
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "UPDATE personas SET name = ?, prompt = ? WHERE id = ?",
            (name, prompt, persona_id),
        )
        return cursor.rowcount > 0


def delete_persona(persona_id: int) -> bool:
    """Delete a persona; return True if it existed."""
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
        return cursor.rowcount > 0


# ──────────────────────────────────────────────────────────────────────────────
# SESSION MAINTENANCE
# ──────────────────────────────────────────────────────────────────────────────


def purge_expired_sessions(max_age_hours: int = 24) -> int:
    """Delete login sessions older than the token lifetime; return how many."""
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM login_sessions WHERE created_at < datetime('now', ?)",
            (f"-{max_age_hours} hours",),
        )
        return cursor.rowcount
