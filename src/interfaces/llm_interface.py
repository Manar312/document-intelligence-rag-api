from abc import ABC, abstractmethod


class LLMInterface(ABC):
    """Contract that every LLM provider must implement."""

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return whether the provider has the required configuration."""
        raise NotImplementedError

    @abstractmethod
    async def generate_answer(
        self,
        question: str,
        contexts: list[dict],
    ) -> str:
        """Generate an answer using the supplied retrieved contexts."""
        raise NotImplementedError
