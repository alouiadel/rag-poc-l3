"""
Data Models - Pydantic request/response schemas for API endpoints

Organized by feature:
- Authentication: RegisterRequest, LoginRequest, LogoutRequest
- Chat: ChatRequest, ChatResponse, ChatSessionInfo, MessageInfo
- Admin: UpdateUserAdminRequest, UserInfoResponse
- RAG: IngestRequest, QueryRequest, FileUploadResponse

All models use Pydantic for automatic validation, serialization, and documentation.
"""


from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION MODELS
# ──────────────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """User registration request (auth.py: register endpoint)"""

    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(
        min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    is_admin: bool = False
    admin_secret: str | None = Field(default=None, max_length=256)


class LoginRequest(BaseModel):
    """User login request (auth.py: login endpoint)"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class LogoutRequest(BaseModel):
    """User logout request (auth.py: logout endpoint)"""

    token: str = Field(min_length=1)


# ──────────────────────────────────────────────────────────────────────────────
# CHAT MODELS
# ──────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Chat message request (chat.py: chat endpoint)"""

    message: str = Field(min_length=1, max_length=8000)
    session_id: int | None = None  # None = new session created automatically
    persona_prompt: str | None = Field(
        default=None, max_length=2000
    )  # Optional persona/system instruction


class ChatResponse(BaseModel):
    """Chat response with answer and session metadata (chat.py: chat endpoint)"""

    answer: str
    session_id: int  # Always returned so frontend knows which session to track
    title: str | None = None  # Session title


class ChatSessionInfo(BaseModel):
    """Chat session metadata (chat.py: list_chat_sessions endpoint)"""

    id: int
    title: str
    created_at: str
    updated_at: str


class MessageInfo(BaseModel):
    """Individual message within a session (chat.py: get_session_messages endpoint)"""

    role: str  # "user" or "assistant"
    content: str


# ──────────────────────────────────────────────────────────────────────────────
# RAG MODELS
# ──────────────────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Query request for RAG endpoint (rag.py: query_endpoint)"""

    message: str = Field(min_length=1, max_length=8000)


class IngestRequest(BaseModel):
    """Document ingestion request (rag.py: ingest_documents)"""

    documents: list[str] = Field(min_length=1, max_length=100)


class FileUploadResponse(BaseModel):
    """Response after file upload and ingestion (rag.py: upload_file)"""

    filename: str
    file_size_kb: float
    characters_extracted: int
    chunks_created: int
    total_chunks: int
    message: str


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN MODELS
# ──────────────────────────────────────────────────────────────────────────────


class UpdateUserAdminRequest(BaseModel):
    """Request to update user admin status (admin.py: update_user_admin endpoint)"""

    target_username: str = Field(min_length=1, max_length=50)
    is_admin: bool


class UserInfoResponse(BaseModel):
    """User information response (admin.py: get_user, list_all_users endpoints)"""

    id: int
    full_name: str
    username: str
    is_admin: bool


# ──────────────────────────────────────────────────────────────────────────────
# PERSONA MODELS
# ──────────────────────────────────────────────────────────────────────────────


class PersonaRequest(BaseModel):
    """Create/update payload for a persona (personas.py)"""

    name: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=1, max_length=500)


class PersonaInfo(BaseModel):
    """Persona returned to clients (personas.py)"""

    id: int
    name: str
    prompt: str
