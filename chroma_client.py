"""
ChromaDB Client Module for Ask-Chopper

Provides connection management and operations for ChromaDB Cloud.
Uses direct HTTP API to avoid Python version compatibility issues.
"""

import os
import httpx
from typing import List, Dict, Optional

# Singleton client instance
_http_client = None
_collection_id = None

COLLECTION_NAME = "ask_chopper_documents"


def _get_http_client():
    """Get or create HTTP client for Chroma Cloud API."""
    global _http_client

    if _http_client is not None:
        return _http_client

    api_key = os.environ.get("CHROMA_API_KEY")
    if not api_key:
        raise ValueError("CHROMA_API_KEY environment variable not set")

    # Strip whitespace/newlines from API key (common copy-paste issue)
    api_key = api_key.strip()

    _http_client = httpx.Client(
        base_url="https://api.trychroma.com",
        headers={
            "x-chroma-token": api_key,
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

    return _http_client


def _get_config():
    """Get Chroma Cloud configuration."""
    tenant = os.environ.get("CHROMA_TENANT")
    database = os.environ.get("CHROMA_DATABASE")

    if not tenant or not database:
        raise ValueError("CHROMA_TENANT and CHROMA_DATABASE must be set")

    return tenant, database


def _ensure_collection():
    """Ensure the collection exists and return its ID."""
    global _collection_id

    if _collection_id:
        return _collection_id

    client = _get_http_client()
    tenant, database = _get_config()

    # List collections to find ours
    response = client.get(
        f"/api/v2/tenants/{tenant}/databases/{database}/collections"
    )
    response.raise_for_status()

    collections = response.json()
    for col in collections:
        if col.get("name") == COLLECTION_NAME:
            _collection_id = col["id"]
            return _collection_id

    # Create collection if it doesn't exist
    response = client.post(
        f"/api/v2/tenants/{tenant}/databases/{database}/collections",
        json={
            "name": COLLECTION_NAME,
            "metadata": {"hnsw:space": "cosine"}
        }
    )
    response.raise_for_status()
    _collection_id = response.json()["id"]
    return _collection_id


def get_chroma_client():
    """Get the HTTP client (for compatibility)."""
    return _get_http_client()


def get_collection():
    """Get collection info (for compatibility)."""
    collection_id = _ensure_collection()

    # Return object with expected attributes
    class CollectionInfo:
        def __init__(self, col_id):
            self.name = COLLECTION_NAME
            self.id = col_id

        def count(self):
            try:
                client = _get_http_client()
                tenant, database = _get_config()
                resp = client.get(
                    f"/api/v2/tenants/{tenant}/databases/{database}/collections/{self.id}/count"
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            return 0

    return CollectionInfo(collection_id)


def add_document_chunks(
    doc_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    user_id: int,
    session_id: str,
    filename: str
) -> int:
    """
    Add document chunks to ChromaDB with metadata for isolation.

    Args:
        doc_id: Unique document identifier (UUID)
        chunks: List of text chunks
        embeddings: List of embedding vectors (matching chunks)
        user_id: User ID for isolation
        session_id: Session ID for isolation
        filename: Original filename

    Returns:
        Number of chunks added
    """
    client = _get_http_client()
    tenant, database = _get_config()

    # Ensure collection exists
    _ensure_collection()

    # Prepare data for batch insertion
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "user_id": str(user_id),
            "session_id": session_id,
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    # Add to collection using collection ID
    collection_id = _ensure_collection()
    response = client.post(
        f"/api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/add",
        json={
            "ids": ids,
            "embeddings": embeddings,
            "documents": chunks,
            "metadatas": metadatas
        }
    )
    response.raise_for_status()

    return len(chunks)


def query_documents(
    query_embedding: List[float],
    user_id: int,
    session_id: str = None,
    n_results: int = 5,
    doc_id: str = None
) -> Dict:
    """
    Query documents with user isolation filtering.

    Args:
        query_embedding: Query embedding vector
        user_id: User ID to filter by (required for isolation)
        session_id: Optional session ID for further filtering
        n_results: Maximum number of results to return
        doc_id: Optional specific document ID to search within

    Returns:
        Dictionary with 'documents', 'metadatas', 'distances' lists
    """
    client = _get_http_client()
    tenant, database = _get_config()

    # Build where filter for isolation
    where_filter = {"user_id": {"$eq": str(user_id)}}

    if session_id and doc_id:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"session_id": {"$eq": session_id}},
                {"doc_id": {"$eq": doc_id}}
            ]
        }
    elif session_id:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"session_id": {"$eq": session_id}}
            ]
        }
    elif doc_id:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"doc_id": {"$eq": doc_id}}
            ]
        }

    try:
        collection_id = _ensure_collection()
        response = client.post(
            f"/api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/query",
            json={
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "where": where_filter,
                "include": ["documents", "metadatas", "distances"]
            }
        )
        response.raise_for_status()
        results = response.json()

        # Flatten results (query returns nested lists)
        return {
            "documents": results.get("documents", [[]])[0] if results.get("documents") else [],
            "metadatas": results.get("metadatas", [[]])[0] if results.get("metadatas") else [],
            "distances": results.get("distances", [[]])[0] if results.get("distances") else []
        }
    except Exception as e:
        print(f"Query error: {e}")
        return {"documents": [], "metadatas": [], "distances": []}


def delete_document(doc_id: str) -> int:
    """
    Delete all chunks for a specific document.

    Args:
        doc_id: Document ID to delete

    Returns:
        Number of chunks deleted (approximate)
    """
    client = _get_http_client()
    tenant, database = _get_config()

    try:
        collection_id = _ensure_collection()
        response = client.post(
            f"/api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/delete",
            json={
                "where": {"doc_id": {"$eq": doc_id}}
            }
        )
        response.raise_for_status()
        return 1  # Approximate - API doesn't return count
    except Exception as e:
        print(f"Delete error: {e}")
        return 0


def delete_user_documents(user_id: int, session_id: str = None) -> int:
    """
    Delete all documents for a user (optionally filtered by session).

    Args:
        user_id: User ID whose documents to delete
        session_id: Optional session ID for further filtering

    Returns:
        Number of chunks deleted (approximate)
    """
    client = _get_http_client()
    tenant, database = _get_config()

    # Build where filter
    if session_id:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"session_id": {"$eq": session_id}}
            ]
        }
    else:
        where_filter = {"user_id": {"$eq": str(user_id)}}

    try:
        collection_id = _ensure_collection()
        response = client.post(
            f"/api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/delete",
            json={"where": where_filter}
        )
        response.raise_for_status()
        return 1  # Approximate
    except Exception as e:
        print(f"Delete user documents error: {e}")
        return 0


def get_document_count(user_id: int, session_id: str = None) -> int:
    """
    Get count of chunks for a user's documents.

    Args:
        user_id: User ID to count for
        session_id: Optional session ID for further filtering

    Returns:
        Number of chunks
    """
    # Note: Chroma Cloud API doesn't have a direct count with filter
    # This is a workaround using query with high limit
    try:
        from document_processor import EMBEDDING_DIMENSIONS
        dummy_embedding = [0.0] * EMBEDDING_DIMENSIONS  # Use zero embedding for count
        results = query_documents(dummy_embedding, user_id, session_id, n_results=1000)
        return len(results.get("documents", []))
    except Exception:
        return 0
