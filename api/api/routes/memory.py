from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import QdrantClient
from api.core.auth import require_current_user
from api.models.user import User
from api.memory.reflection import SemanticMemory

router = APIRouter()

@router.get("/")
async def list_memories(current_user: User = Depends(require_current_user)):
    """List semantic memories (reflected facts) from Qdrant."""
    try:
        qclient = QdrantClient(url="http://localhost:6333")
        collection_name = SemanticMemory.COLLECTION
        
        # Check if collection exists
        collections = qclient.get_collections().collections
        if collection_name not in [c.name for c in collections]:
            return {"memories": []}
            
        # Scroll points (paginated retrieval)
        results, next_page = qclient.scroll(
            collection_name=collection_name,
            limit=50,
            with_payload=True,
            with_vectors=False
        )
        
        memories = [
            {
                "id": hit.id,
                "text": hit.payload.get("text"),
                "session_id": hit.payload.get("session_id"),
                "timestamp": hit.payload.get("timestamp") # May be missing
            }
            for hit in results
            if hit.payload and hit.payload.get("text")
        ]
        
        return {"memories": memories}
    except Exception as e:
        return {"memories": [], "error": str(e)}
