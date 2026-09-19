from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        ...

    @abstractmethod
    def chat_stream(self, messages: list[dict],
                    model: str | None = None) -> AsyncIterator[str]:
        ...
