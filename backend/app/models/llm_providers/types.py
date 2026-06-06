from enum import Enum 

class ProviderType(str, Enum):
    GROQ = "groq"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"