"""
Chat Endpoints - for managing multi-turn conversations with RAG-powered responses

KEY CONCEPTS:
- Each user has multiple independent chat sessions
- Each session stores conversation history (user + assistant messages)
- RAG (Retrieval-Augmented Generation) provides context-aware responses from documents
- Session title auto-generated on first message using LLM (Ollama)
- Token validation via check_token ensures only authenticated users can access their sessions
- session_belongs_to_user() enforces ownership: users can only access/modify their own sessions

Functions:
- chat(): Main conversation endpoint. Creates/reuses session, generates RAG response, saves history, generates title for first message.
- new_chat_session(): Create new empty session for "New Chat" button.
- list_chat_sessions(): Retrieve all sessions for logged-in user (sidebar display).
- get_session_messages(): Load all messages from a specific session (reload conversation).
- remove_chat_session(): Delete a session and cascade-delete all its messages.
"""

import logging

from fastapi import Depends, HTTPException
from models import ChatRequest, ChatResponse, ChatSessionInfo, MessageInfo
from services.database import (
    create_chat_session,
    delete_chat_session,
    get_chat_sessions,
    get_messages,
    get_session_title,
    save_message,
    session_belongs_to_user,
    update_session_title,
)
from services.rag_service import generate_chat_response, generate_session_title

from core_endpoints.auth import check_token

logger = logging.getLogger(__name__)


def chat(payload: ChatRequest, user_data: dict = Depends(check_token)) -> ChatResponse:
    """
    Main chat endpoint - process user message and generate RAG-powered response.

    Args:
        payload (ChatRequest): Contains message text and optional session_id to continue existing conversation.
        user_data (dict): Authenticated user info from check_token dependency (contains user_id).

    Returns:
        ChatResponse: Contains answer text, session_id, and auto-generated title (only on first message).

    Raises:
        HTTPException(400): If message is empty or whitespace-only.
        HTTPException(404): If provided session_id does not belong to authenticated user.
        HTTPException(500): If system error occurs during processing.

    Process:
        1. Create new session if no session_id provided, else verify ownership
        2. Load up to 50 recent messages from database (full conversation context)
        3. Generate response using RAG service (Ollama LLM with document retrieval)
        4. Save both user message and assistant response to database
        5. If first message in session (title still "New chat"), generate and save new title
        6. Return response with session_id and auto-generated title (if applicable)

    Note:
        - Title generation happens once per session (on first message)
        - Full message history loaded for context (improves response quality)
        - All messages persisted to enable conversation reload
    """
    try:
        user_id = user_data["user_id"]
        user_message = payload.message.strip()

        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # Get or create session
        session_id = payload.session_id
        is_new_session = session_id is None

        if is_new_session:
            session_id = create_chat_session(user_id)
        else:
            # Verify that session belongs to this user (ownership check)
            if not session_belongs_to_user(session_id, user_id):
                raise HTTPException(status_code=404, detail="Session not found")

        # Load real conversation history from database (max 50 messages = 25 exchanges)
        history = get_messages(session_id, limit=50)

        # Generate response with full context via RAG + Ollama
        answer = generate_chat_response(
            question=user_message,
            history=history,
            persona_prompt=payload.persona_prompt,
        )

        # Persist both user message and assistant response to database
        save_message(session_id, "user", user_message)
        save_message(session_id, "assistant", answer)

        # Generate title automatically on first message of session
        # Check current title in DB - if still "New chat", this is first exchange
        # (regardless of whether session_id was provided or newly created)
        generated_title = None
        current_title = get_session_title(session_id)
        if current_title == "New chat":
            generated_title = generate_session_title(user_message, answer)
            update_session_title(session_id, generated_title)

        return ChatResponse(answer=answer, session_id=session_id, title=generated_title)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Chat endpoint failed")
        raise HTTPException(status_code=500, detail="Chat system error") from None


def new_chat_session(user_data: dict = Depends(check_token)) -> ChatSessionInfo:
    """
    Create new empty chat session.

    Args:
        user_data (dict): Authenticated user info from check_token dependency (contains user_id).

    Returns:
        ChatSessionInfo: New session object with default title "New chat", timestamps, and session_id.

    Raises:
        HTTPException(500): If session creation fails unexpectedly.

    Use Case:
        Called by "New Chat" button from frontend to start fresh conversation.
        Returns initialized session ready for first message.
    """
    user_id = user_data["user_id"]
    session_id = create_chat_session(user_id)
    sessions = get_chat_sessions(user_id)
    session = next((s for s in sessions if s["id"] == session_id), None)
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")
    return ChatSessionInfo(**session)


def list_chat_sessions(user_data: dict = Depends(check_token)) -> list[ChatSessionInfo]:
    """
    Retrieve all chat sessions for logged-in user.

    Args:
        user_data (dict): Authenticated user info from check_token dependency (contains user_id).

    Returns:
        list[ChatSessionInfo]: List of all user's sessions with titles, timestamps, and session IDs.

    Use Case:
        Called to populate sidebar/conversation list in frontend.
        Enables user to see all past conversations and switch between them.
    """
    user_id = user_data["user_id"]
    sessions = get_chat_sessions(user_id)
    return [ChatSessionInfo(**s) for s in sessions]


def get_session_messages(
    session_id: int,
    user_data: dict = Depends(check_token),
) -> list[MessageInfo]:
    """
    Load all messages from a specific chat session.

    Args:
        session_id (int): ID of the session to retrieve messages from.
        user_data (dict): Authenticated user info from check_token dependency (contains user_id).

    Returns:
        list[MessageInfo]: All messages in the session (user and assistant) in chronological order.

    Raises:
        HTTPException(404): If session does not exist or does not belong to authenticated user (ownership check).

    Use Case:
        Called when user clicks on a past conversation to reload its full message history.
        Enables context preservation when switching between sessions.
    """
    user_id = user_data["user_id"]

    if not session_belongs_to_user(session_id, user_id):
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages(session_id, limit=200)
    return [MessageInfo(**m) for m in messages]


def remove_chat_session(
    session_id: int,
    user_data: dict = Depends(check_token),
) -> dict:
    """
    Delete a chat session and cascade-delete all its messages.

    Args:
        session_id (int): ID of the session to delete.
        user_data (dict): Authenticated user info from check_token dependency (contains user_id).

    Returns:
        dict: Success message confirming deletion.

    Raises:
        HTTPException(404): If session does not exist or does not belong to authenticated user (ownership check).

    Cascade Behavior:
        - Deletes session record from chat_sessions table
        - Cascade-deletes all related messages from chat_messages table (database enforces via FK)

    Use Case:
        Called by "Delete conversation" button in frontend to remove past sessions.
    """
    user_id = user_data["user_id"]
    deleted = delete_chat_session(session_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": f"Session {session_id} deleted"}
