from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self):
        # We use a small local CPU model to save GPU VRAM for Ollama
        self.model_name = "all-MiniLM-L6-v2" 
        logger.info(f"Loading CPU Embedding Model: {self.model_name}. This avoids VRAM overhead.")
        self.model = SentenceTransformer(self.model_name, device="cpu")
        
    def generate_embedding(self, text: str):
        return self.model.encode(text).tolist()
