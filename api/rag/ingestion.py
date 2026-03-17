import uuid
from api.rag.vector_store import QdrantManager
from api.rag.embeddings import EmbeddingManager
from qdrant_client.models import PointStruct

class DocumentIngestor:
    def __init__(self):
        self.qdrant = QdrantManager()
        self.embedder = EmbeddingManager()
        
    def chunk_text(self, text: str, chunk_size: int = 1000):
        # Simple character chunking
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
    async def ingest_document(self, text: str, collection_name: str, metadata: dict = None):
        await self.qdrant.create_collection_if_not_exists(collection_name)
        chunks = self.chunk_text(text)
        
        points = []
        for chunk in chunks:
            vector = self.embedder.generate_embedding(chunk)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"text": chunk, **(metadata or {})}
            )
            points.append(point)
            
        await self.qdrant.client.upsert(collection_name=collection_name, points=points)
        return len(chunks)
