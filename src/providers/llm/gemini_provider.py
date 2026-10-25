from src.core.config import Settings
from src.providers.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class GeminiProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout=settings.llm_timeout_seconds,
        )
