import os

import uvicorn
from config import app
from core_endpoints.admin import get_user, list_all_users, update_user_admin
from core_endpoints.auth import login, logout, register
from core_endpoints.chat import (
    chat,
    get_session_messages,
    list_chat_sessions,
    new_chat_session,
    remove_chat_session,
)
from core_endpoints.personas import (
    add_persona,
    edit_persona,
    get_personas,
    remove_persona,
)
from core_endpoints.rag import (
    collection_info,
    ingest_documents,
    query_endpoint,
    reset_vector_store,
    upload_file,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ──────────────────────────────────────────────────────────────────────────────
# STATIC FILES & FRONTEND SERVING
# ──────────────────────────────────────────────────────────────────────────────

# Mount front-end static files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "front-end")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


# Serve login page as default (root route)
@app.get("/")
async def serve_login():
    login_path = os.path.join(frontend_path, "login", "login.html")
    return FileResponse(login_path)


# Serve chat page
@app.get("/chat")
async def serve_chat():
    chat_path = os.path.join(frontend_path, "chat", "chat.html")
    return FileResponse(chat_path)


# Serve admin page
@app.get("/admin")
async def serve_admin():
    admin_path = os.path.join(frontend_path, "admin", "admin.html")
    return FileResponse(admin_path)


# Serve stats page
@app.get("/stats")
async def serve_stats():
    stats_path = os.path.join(frontend_path, "stats", "stats.html")
    return FileResponse(stats_path)


# ──────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ──────────────────────────────────────────────────────────────────────────────

# Auth routes
app.post("/register")(register)
app.post("/login")(login)
app.post("/logout")(logout)

# Chat routes
app.post("/chat")(chat)
app.post("/chat/new")(new_chat_session)
app.get("/chat/sessions")(list_chat_sessions)
app.get("/chat/sessions/{session_id}/messages")(get_session_messages)
app.delete("/chat/sessions/{session_id}")(remove_chat_session)

# Admin routes
app.get("/user")(get_user)
app.get("/users")(list_all_users)
app.post("/update-user-admin")(update_user_admin)

# Persona routes
app.get("/personas")(get_personas)
app.post("/personas")(add_persona)
app.put("/personas/{persona_id}")(edit_persona)
app.delete("/personas/{persona_id}")(remove_persona)

# RAG routes
app.get("/collection-info")(collection_info)
app.post("/ingest")(ingest_documents)
app.post("/upload")(upload_file)
app.post("/reset-collection")(reset_vector_store)
app.post("/query")(query_endpoint)


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
