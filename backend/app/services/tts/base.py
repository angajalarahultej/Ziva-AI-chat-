from abc import ABC, abstractmethod


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, language: str, out_path: str,
                         voice_name: str = "Female") -> str:
        """Write audio to out_path, return out_path."""
        ...
