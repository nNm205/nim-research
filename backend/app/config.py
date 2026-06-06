from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str 
    DEBUG: bool 

    # Database
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str                  
    JWT_ALGORITHM: str           
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Redis
    REDIS_URL: str 

    # Embedding Providers 
    GOOGLEAI_API_KEY: str 
    HUGGINGFACE_API_KEY: str 
    JINA_API_KEY: str 
    EMBEDDING_PROVIDER: str 
    EMBEDDING_MODEL: str 

    # LLM Provider 
    GROQ_API_KEY: str 
    GROQ_BASE_URL: str 
    MODEL_NAME: str 
    PROVIDER: str 

    OPENROUTER_API_KEY: str 
    OPENROUTER_BASE_URL: str 
    OPENAI_API_KEY: str 
    OPENAI_BASE_URL: str 
    CLAUDE_API_KEY: str 
    CLAUDE_BASE_URL: str 

    # Search API 
    SERP_API_KEY: str
    SEMANTIC_API_KEY: str 

    class Config: 
        env_file = ".env"

settings = Settings()