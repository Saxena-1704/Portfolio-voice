import sounddevice as sd
import numpy as np
from typing import Callable, Optional


class Microphone:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 320,
        channels: int = 1,
        dtype: str = "int16",
        device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self._stream: Optional[sd.InputStream] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        if self._stream is not None:
            raise RuntimeError("Microphone already running")

        self._callback = callback
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            device=self.device,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._callback = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None and self._stream.active

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            print(f"Mic status: {status}")
        if self._callback is not None:
            self._callback(indata.copy().flatten())

    @staticmethod
    def list_devices() -> None:
        print(sd.query_devices())

    @staticmethod
    def get_default_input_device() -> int:
        in_dev = sd.default.device[0]
        if in_dev is None:
            raise RuntimeError("No default input device found")
        return in_dev
