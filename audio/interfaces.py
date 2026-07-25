from abc import ABC, abstractmethod
from typing import Any

class IAudioSource(ABC):
    @abstractmethod
    def ReadFrames(self, num_frames: int) -> bytes:
        """Read and return PCM frames as bytes (immutable)."""
        raise NotImplementedError()

    @abstractmethod
    def Seek(self, position: int) -> None:
        """Seek to frame position."""
        raise NotImplementedError()

    @abstractmethod
    def Stop(self) -> None:
        """Stop the source and release resources."""
        raise NotImplementedError()


class IAudioMixer(ABC):
    @abstractmethod
    def AddSource(self, source: IAudioSource) -> None:
        raise NotImplementedError()

    @abstractmethod
    def RemoveSource(self, source: IAudioSource) -> None:
        raise NotImplementedError()

    @abstractmethod
    def Mix(self, num_frames: int) -> bytes:
        """Return mixed immutable PCM bytes for num_frames."""
        raise NotImplementedError()


class IAudioOutput(ABC):
    @abstractmethod
    def Start(self, sample_rate: int, channels: int, sample_format: Any) -> None:
        raise NotImplementedError()

    @abstractmethod
    def WriteFrames(self, pcm_bytes: bytes) -> None:
        raise NotImplementedError()

    @abstractmethod
    def Stop(self) -> None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def DeviceId(self) -> str:
        raise NotImplementedError()
