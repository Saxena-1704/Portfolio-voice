import asyncio
import numpy as np
from abc import ABC, abstractmethod
from typing import Callable, AsyncIterator


class AudioDevice(ABC):
    @abstractmethod
    async def start(self, on_audio: Callable) -> None:
        ...

    @abstractmethod
    async def play(self, stream: AsyncIterator[np.ndarray]) -> None:
        ...

    @abstractmethod
    async def stop_playback(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
