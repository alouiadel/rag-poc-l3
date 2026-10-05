"""
RAG API Endpoints - Document ingestion and semantic search

Provides REST endpoints for:
- Managing Qdrant vector database collections (document storage)
- Ingesting documents and files (text extraction + embeddings)
- Querying the RAG system (semantic search with LLM)
- Resetting collections

Key Concepts:
- RAG (Retrieval-Augmented Generation): Uses document embeddings for semantic search
  to enhance LLM responses with relevant context from uploaded documents
- Supported formats: PDF, TXT, DOCX, PPTX (extracted via extract_text_from_file)
- File size limit: 20 MB per file
"""

from fastapi import Depends, File, HTTPException, UploadFile
from models import ChatResponse, FileUploadResponse, IngestRequest, QueryRequest
from services.rag_service import (
    SUPPORTED_EXTENSIONS,
    add_documents,
    extract_text_from_file,
    get_collection_info,
    get_file_extension,
    query_rag,
    reset_collection,
)

from core_endpoints.auth import check_token, require_admin

# ── Endpoints ─────────────────────────────────────────────────────────────────

# Magic bytes used to sanity-check that an upload matches its extension.
SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),
}


def _validate_content(ext: str, content: bytes) -> None:
    """Reject files whose content does not match the declared extension."""
    expected = SIGNATURES.get(ext)
    if expected and not content.startswith(expected):
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match the '{ext}' type.",
        )
    if ext in (".txt", ".md") and b"\x00" in content[:8192]:
        raise HTTPException(
            status_code=400,
            detail="Text file appears to contain binary data.",
        )



def collection_info(_admin: dict = Depends(require_admin)):
    """
    Get collection statistics from Qdrant vector database.

    Returns:
        dict: Collection info including vector count, collection name, and dimensions.
              Format: {"status": "success", "vector_count": int, "collection": str, ...}

    Raises:
        HTTPException(500): If Qdrant query fails.

    Use Case:
        Check current state of document vector store (admin monitoring).
    """
    result = get_collection_info()
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


def ingest_documents(
    request: IngestRequest,
    _admin: dict = Depends(require_admin),
) -> dict:
    """
    Ingest raw text documents into RAG vector store.

    Args:
        request (IngestRequest): Contains list of text strings to embed and store.

    Returns:
        dict: Ingestion result with status, chunks created, and total chunks.
              Format: {"status": "success", "chunks_created": int, "total_chunks": int}

    Raises:
        HTTPException(400): If no documents provided.
        HTTPException(500): If Qdrant ingestion fails.

    Note:
        - Each document is split into chunks (default ~300 tokens each)
        - Chunks are vectorized and stored in Qdrant collection
    """
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    result = add_documents(request.documents)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


async def upload_file(
    file: UploadFile = File(...),
    _user: dict = Depends(check_token),
) -> FileUploadResponse:
    """
    Upload and ingest a file into RAG vector store.

    Args:
        file (UploadFile): File to upload (PDF, TXT, DOCX, PPTX).

    Returns:
        FileUploadResponse: Ingestion summary with filename, size, text extracted, chunks created.

    Raises:
        HTTPException(400): If unsupported file type or empty file.
        HTTPException(413): If file exceeds 20 MB size limit.
        HTTPException(422): If text extraction fails (malformed file).
        HTTPException(500): If Qdrant ingestion fails.

    Process:
        1. Validate file type (check extension against SUPPORTED_EXTENSIONS)
        2. Read file content with size guard (max 20 MB)
        3. Extract text from file (handles PDF, DOCX, PPTX, TXT)
        4. Split text into chunks and embed via Qdrant
        5. Return ingestion statistics

    Note:
        - Supported formats: PDF, TXT, DOCX, PPTX
        - File size limit: 20 MB
    """
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
    CHUNK_SIZE = 1024 * 1024

    filename = file.filename or "upload"
    ext = get_file_extension(filename)

    # Validate file type
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Read in chunks so an oversized upload is rejected before buffering it all.
    buffer = bytearray()
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum: 20 MB.",
            )

    content = bytes(buffer)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    _validate_content(ext, content)

    # Extract text
    try:
        text = extract_text_from_file(filename, content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=500, detail="Failed to process the uploaded file."
        ) from e

    # Ingest into vector store
    result = add_documents([text])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return FileUploadResponse(
        filename=filename,
        file_size_kb=round(len(content) / 1024, 1),
        characters_extracted=len(text),
        chunks_created=result["chunks_created"],
        total_chunks=result["total_chunks"],
        message=f"'{filename}' uploaded and ingested successfully.",
    )


def query_endpoint(
    request: QueryRequest,
    _user: dict = Depends(check_token),
) -> ChatResponse:
    """
    Query the RAG system with semantic search over ingested documents.

    Args:
        request (QueryRequest): Contains user query string.

    Returns:
        ChatResponse: LLM response with answer to the query (session_id=0 for non-auth testing).

    Raises:
        HTTPException(500): If Qdrant search or Ollama inference fails.

    Process:
        1. Embed user query via Ollama embeddings model
        2. Search Qdrant collection for semantically similar documents (top-k retrieval)
        3. Pass query + retrieved context to Ollama LLM for generation
        4. Return generated answer

    Note:
        - Context comes from database via documents ingested via upload_file() or ingest_documents()
        - Respects session_id=0 (non-persistent result, testing only)
    """
    answer = query_rag(request.message)
    return ChatResponse(answer=answer, session_id=0)


def reset_vector_store(_admin: dict = Depends(require_admin)) -> dict:
    """
    Delete all documents from Qdrant vector store (destructive operation).

    Returns:
        dict: Reset result with status and message.
              Format: {"status": "success", "message": "Collection cleared"}

    Raises:
        HTTPException(500): If Qdrant connection fails.

    WARNING - DESTRUCTIVE OPERATION:
        - Deletes ALL vector embeddings and document references permanently
        - No recovery possible; requires re-ingesting documents
        - Consider exporting data before reset if needed

    Use Cases:
        - Clear stale/corrupted embeddings before re-ingesting
        - Start with fresh knowledge base for new environment
        - Maintenance/cleanup operations
    """
    result = reset_collection()
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
