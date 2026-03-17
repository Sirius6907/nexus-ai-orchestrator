"""
Semantic Memory — Extracts and stores key facts from conversations,
retrieves relevant memories for future sessions.
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Long-term memory using Qdrant vector storage."""

    COLLECTION = "semantic_memory"
    EMBED_MODEL = "nomic-embed-text"

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url

    async def extract_and_store(
        self,
        conversation_text: str,
        session_id: str,
        llm_manager=None,
    ) -> int:
        """
        Extract key facts from a conversation and store as memories.

        Returns number of memories stored.
        """
        if not llm_manager:
            return 0

        # Step 1: Extract key facts via LLM
        extraction_prompt = (
            "Extract the 3 most important facts or decisions from this "
            "conversation. Output each fact on a separate line, prefixed "
            "with 'FACT: '. Be concise.\n\n"
            f"CONVERSATION:\n{conversation_text[:3000]}"
        )

        try:
            response = await llm_manager.chat(
                model="gemma3:1b",
                messages=[{"role": "user", "content": extraction_prompt}],
                unload_after=True,
            )

            facts = [
                line.replace("FACT:", "").strip()
                for line in response.split("\n")
                if line.strip().upper().startswith("FACT:")
            ]

            if not facts:
                return 0

            # Step 2: Embed and store each fact
            stored = 0
            for fact in facts[:5]:  # Max 5 facts per conversation
                success = await self._store_memory(fact, session_id)
                if success:
                    stored += 1

            logger.info(f"Stored {stored} memories from session {session_id}")
            return stored

        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return 0

    async def retrieve_relevant(
        self, query: str, top_k: int = 3
    ) -> list[str]:
        """Retrieve relevant memories for a new conversation."""
        try:
            # Generate query embedding
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/embed",
                    json={"model": self.EMBED_MODEL, "input": query},
                )
                if resp.status_code != 200:
                    return []

                embedding = resp.json().get("embeddings", [[]])[0]
                if not embedding:
                    return []

            # Search Qdrant
            from qdrant_client import QdrantClient

            qclient = QdrantClient(url="http://localhost:6333")

            collections = qclient.get_collections().collections
            if self.COLLECTION not in [c.name for c in collections]:
                return []

            results = qclient.search(
                collection_name=self.COLLECTION,
                query_vector=embedding,
                limit=top_k,
            )

            return [
                hit.payload.get("text", "")
                for hit in results
                if hit.payload and hit.payload.get("text")
            ]

        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            return []

    async def _store_memory(self, text: str, session_id: str) -> bool:
        """Embed a memory and store in Qdrant."""
        try:
            import uuid

            # Generate embedding
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/embed",
                    json={"model": self.EMBED_MODEL, "input": text},
                )
                if resp.status_code != 200:
                    return False

                embedding = resp.json().get("embeddings", [[]])[0]
                if not embedding:
                    return False

            # Store in Qdrant
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct, VectorParams, Distance

            qclient = QdrantClient(url="http://localhost:6333")

            # Ensure collection exists
            collections = qclient.get_collections().collections
            if self.COLLECTION not in [c.name for c in collections]:
                qclient.create_collection(
                    collection_name=self.COLLECTION,
                    vectors_config=VectorParams(
                        size=len(embedding),
                        distance=Distance.COSINE,
                    ),
                )

            qclient.upsert(
                collection_name=self.COLLECTION,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload={
                            "text": text,
                            "session_id": session_id,
                        },
                    )
                ],
            )
            return True

        except Exception as e:
            logger.error(f"Memory storage failed: {e}")
            return False
