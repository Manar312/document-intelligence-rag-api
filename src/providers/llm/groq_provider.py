from src.core.config import Settings
from src.providers.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            timeout=settings.llm_timeout_seconds,
        )
