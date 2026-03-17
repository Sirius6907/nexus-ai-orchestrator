"""
Research Agent — RAG-powered research using Qdrant vector database.
"""
import logging
from api.llm.ollama_client import OllamaManager

logger = logging.getLogger(__name__)


class ResearchAgent:
    def __init__(self, llm_manager: OllamaManager):
        self.llm_manager = llm_manager

    async def execute_research(
        self,
        query: str,
        collection_name: str = "documents",
        research_model: str = "gemma3:1b",
    ) -> str:
        """
        Search the vector database for relevant context, then synthesize
        a research response using the LLM.
        """
        # Step 1: Retrieve relevant context from Qdrant
        context_chunks = await self._search_qdrant(query, collection_name)

        if not context_chunks:
            return await self._direct_research(query, research_model)

        # Step 2: Synthesize with LLM
        context_text = "\n\n---\n\n".join(context_chunks)
        system_prompt = (
            "You are a research assistant. Use the provided context to answer "
            "the user's question. Cite relevant parts of the context. "
            "If the context doesn't contain the answer, say so clearly."
        )

        user_content = (
            f"CONTEXT:\n{context_text[:3000]}\n\n"
            f"QUESTION: {query}"
        )

        response = await self.llm_manager.chat(
            model=research_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            unload_after=True,
        )
        return response

    async def _direct_research(self, query: str, model: str) -> str:
        """Fallback: research without RAG context."""
        response = await self.llm_manager.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a knowledgeable research assistant. Answer thoroughly.",
                },
                {"role": "user", "content": query},
            ],
            unload_after=True,
        )
        return response

    async def _search_qdrant(
        self, query: str, collection_name: str, top_k: int = 5
    ) -> list[str]:
        """Search Qdrant for relevant document chunks."""
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url="http://localhost:6333")

            # Check if collection exists
            collections = client.get_collections().collections
            coll_names = [c.name for c in collections]
            if collection_name not in coll_names:
                logger.info(f"Collection '{collection_name}' not found in Qdrant")
                return []

            # Generate query embedding via Ollama
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.post(
                    "http://localhost:11434/api/embed",
                    json={"model": "nomic-embed-text", "input": query},
                )
                if resp.status_code != 200:
                    logger.warning("Embedding model not available, skipping RAG")
                    return []

                embedding = resp.json().get("embeddings", [[]])[0]

            if not embedding:
                return []

            # Search Qdrant
            results = client.search(
                collection_name=collection_name,
                query_vector=embedding,
                limit=top_k,
            )

            return [
                hit.payload.get("text", "")
                for hit in results
                if hit.payload and hit.payload.get("text")
            ]

        except Exception as e:
            logger.warning(f"Qdrant search failed: {e}")
            return []
