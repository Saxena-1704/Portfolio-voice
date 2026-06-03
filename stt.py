import asyncio
import numpy as np
from faster_whisper import WhisperModel


class SpeechToText:
    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "auto",
        compute_type: str = "int8",
        language: str = "en",
    ):
        self.language = language
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        audio_float = audio.astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio_float, language=self.language)
        return " ".join(seg.text.strip() for seg in segments)

    async def transcribe_async(self, audio: np.ndarray) -> str:
        return await asyncio.to_thread(self.transcribe, audio)
