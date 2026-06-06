from typing import Optional
from app.models.llm_providers.base import LLMProvider
from app.models.llm_providers.groq_provider import GroqProvider
from app.models.llm_providers.openrouter_provider import OpenRouterProvider
from app.models.llm_providers.openai_provider import OpenAIProvider
from app.models.llm_providers.claude_provider import ClaudeProvider 
from app.models.llm_providers.gemini_provider import GeminiProvider
from app.models.llm_providers.types import ProviderType
from app.config import settings 

PROVIDERS = {
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.CLAUDE: ClaudeProvider,
    ProviderType.GROQ: GroqProvider,
    ProviderType.OPENROUTER: OpenRouterProvider,
    ProviderType.GEMINI: GeminiProvider,
}

DEFAULT_API_KEY = {
    ProviderType.OPENAI: settings.OPENAI_API_KEY,
    ProviderType.CLAUDE: settings.CLAUDE_API_KEY,
    ProviderType.GROQ: settings.GROQ_API_KEY,
    ProviderType.OPENROUTER: settings.OPENROUTER_API_KEY,
    ProviderType.GEMINI: settings.GOOGLEAI_API_KEY,
}

DEFAULT_MODELS = {
    ProviderType.OPENAI: "gpt-4o-mini",
    ProviderType.CLAUDE: "claude-3-haiku",
    ProviderType.GROQ: "openai/gpt-oss-20b",
    ProviderType.OPENROUTER: "openai/gpt-4o-mini",
    ProviderType.GEMINI: "gemini-2.5-flash",
}

class LLMFactory:
    @staticmethod
    def create_provider(
        provider: ProviderType,
        api_key: Optional[str] = None,
        model: str | None = None 
    ) -> LLMProvider: 
        provider_class = PROVIDERS.get(provider)
        if not provider_class:
            raise ValueError(f"Unsupported provider: {provider}")

        api_key = api_key or DEFAULT_API_KEY[provider]
        if not api_key:
            raise ValueError(f"Missing API Key for provider: {provider}")

        return provider_class(
            api_key=api_key,
            model=model or DEFAULT_MODELS[provider]
        )