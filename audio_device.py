import asyncio
import numpy as np
import sounddevice as sd
from abc import ABC, abstractmethod
from collections import deque
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


class LocalAudioDevice(AudioDevice):
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 320):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._input_stream: sd.InputStream | None = None
        self._output_stream: sd.OutputStream | None = None
        self._playback_buffer: deque[np.ndarray] = deque()
        self._playing = False
        self._on_audio: Callable | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self, on_audio: Callable) -> None:
        self._loop = asyncio.get_running_loop()
        self._on_audio = on_audio
        self._input_stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            dtype="int16",
            channels=1,
            callback=self._input_callback,
        )
        self._input_stream.start()

    def _input_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        if status:
            print(f"Mic status: {status}")
        if self._on_audio:
            asyncio.run_coroutine_threadsafe(
                self._on_audio(indata.copy().flatten()), self._loop
            )

    def _output_callback(
        self, outdata: np.ndarray, frames: int, time_info, status
    ) -> None:
        if self._playback_buffer:
            chunk = self._playback_buffer.popleft()
            n = min(len(chunk), frames)
            outdata[:n, 0] = chunk[:n]
            if n < frames:
                outdata[n:, 0] = 0
            if len(chunk) > frames:
                self._playback_buffer.appendleft(chunk[frames:])
        else:
            outdata.fill(0)

    async def play(self, stream: AsyncIterator[np.ndarray]) -> None:
        self._playing = True
        self._playback_buffer.clear()

        self._output_stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            callback=self._output_callback,
        )
        self._output_stream.start()

        async for chunk in stream:
            if not self._playing:
                break
            self._playback_buffer.append(chunk)

        while self._playing and self._playback_buffer:
            await asyncio.sleep(0.01)

        self._stop_output()

    async def stop_playback(self) -> None:
        self._playing = False
        self._playback_buffer.clear()
        self._stop_output()

    def _stop_output(self) -> None:
        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

    async def close(self) -> None:
        await self.stop_playback()
        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None
