from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance
from api.core.config import settings
import logging

logger = logging.getLogger(__name__)

class QdrantManager:
    def __init__(self):
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)
        
    async def create_collection_if_not_exists(self, collection_name: str, vector_size: int = 384):
        exists = await self.client.collection_exists(collection_name)
        if not exists:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
            
    async def search(self, collection_name: str, query_vector: list, limit: int = 3):
        return await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
