import asyncio
import time
import numpy as np
from typing import Callable, AsyncIterator
from fastapi import WebSocket, WebSocketDisconnect
from audio_device import AudioDevice


class BrowserAudioDevice(AudioDevice):
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self._on_audio: Callable | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._playing = False
        self._stop_evt = asyncio.Event()
        self._call_ended = asyncio.Event()
        self._reader_task: asyncio.Task | None = None

    async def start(self, on_audio: Callable) -> None:
        self._loop = asyncio.get_running_loop()
        self._on_audio = on_audio
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while True:
                msg = await self.ws.receive_bytes()
                chunk = np.frombuffer(msg, dtype=np.int16)
                if self._on_audio:
                    await self._on_audio(chunk)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            self._call_ended.set()

    async def play(self, stream: AsyncIterator[np.ndarray]) -> None:
        self._playing = True
        self._stop_evt.clear()
        next_target = time.monotonic()
        try:
            async for chunk in stream:
                if self._stop_evt.is_set():
                    break
                await self.ws.send_bytes(chunk.tobytes())
                if self._stop_evt.is_set():
                    break
                next_target += len(chunk) / 16000
                now = time.monotonic()
                if now < next_target:
                    await asyncio.sleep(next_target - now)
        finally:
            self._playing = False

    async def stop_playback(self) -> None:
        self._stop_evt.set()

    async def wait_for_call_end(self) -> None:
        await self._call_ended.wait()

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
