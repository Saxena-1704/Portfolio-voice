import os
import asyncio
import numpy as np
from edge_tts import Communicate


_FFMPEG_PATH = os.path.join(
    os.environ.get("TEMP", ""),
    "opencode", "ffmpeg", "ffmpeg.exe",
)


class TextToSpeech:
    def __init__(
        self,
        voice: str = "en-US-AriaNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self._stopped = False
        self._ffmpeg_proc = None

    def stop(self) -> None:
        self._stopped = True
        if self._ffmpeg_proc and self._ffmpeg_proc.returncode is None:
            self._ffmpeg_proc.kill()

    async def synthesize_stream(self, text: str):
        self._stopped = False
        tts = Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch,
        )

        proc = await asyncio.create_subprocess_exec(
            _FFMPEG_PATH,
            "-i", "pipe:0",
            "-f", "s16le",
            "-ac", "1",
            "-ar", "16000",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._ffmpeg_proc = proc

        async def feed():
            try:
                async for chunk in tts.stream():
                    if self._stopped:
                        break
                    if chunk["type"] == "audio":
                        proc.stdin.write(chunk["data"])
                        await proc.stdin.drain()
            except BrokenPipeError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        feed_task = asyncio.create_task(feed())

        try:
            while True:
                data = await proc.stdout.read(4096)
                if not data:
                    break
                if len(data) % 2 != 0:
                    data = data[:-1]
                if data:
                    yield np.frombuffer(data, dtype=np.int16)
        finally:
            await feed_task
            self._ffmpeg_proc = None
            try:
                if proc.returncode is None:
                    proc.kill()
                await proc.wait()
            except Exception:
                pass

    async def synthesize(self, text: str) -> bytes:
        chunks: list[bytes] = []
        async for pcm in self.synthesize_stream(text):
            chunks.append(pcm.tobytes())
        return b"".join(chunks)
