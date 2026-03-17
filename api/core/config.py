from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexus AI Platform"
    POSTGRES_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nexus"
    REDIS_URI: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_IMMEDIATELY"
    
    # 4GB VRAM specific settings
    MAX_VRAM_MODELS_LOADED: int = 1
    PLANNER_MODEL: str = "gemma3:1b"
    CODER_MODEL: str = "gemma3:1b"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
