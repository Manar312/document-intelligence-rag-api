from src.core.config import Settings
from src.interfaces.llm_interface import LLMInterface
from src.providers.llm.gemini_provider import GeminiProvider
from src.providers.llm.groq_provider import GroqProvider
from src.providers.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)
from src.providers.llm.openai_provider import OpenAIProvider


def create_llm_provider(settings: Settings) -> LLMInterface:
    """Create the LLM provider selected in application settings."""

    if settings.llm_provider == "openai":
        # Support existing .env values during migration.
        if (
            not settings.openai_api_key.get_secret_value()
            and settings.llm_api_key.get_secret_value()
        ):
            return OpenAICompatibleProvider(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout=settings.llm_timeout_seconds,
            )
        return OpenAIProvider(settings)

    if settings.llm_provider == "gemini":
        return GeminiProvider(settings)

    if settings.llm_provider == "groq":
        return GroqProvider(settings)

    raise ValueError(
        f"Unsupported LLM provider: {settings.llm_provider}"
    )
