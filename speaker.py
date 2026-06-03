import os
import subprocess
import struct
import numpy as np
import sounddevice as sd


_FFMPEG_PATH = os.path.join(
    os.environ.get("TEMP", ""),
    "opencode", "ffmpeg", "ffmpeg.exe",
)


class Speaker:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def play(self, audio: bytes) -> None:
        pcm = self._decode_to_pcm(audio)
        sd.play(pcm, self.sample_rate)

    def stop(self) -> None:
        sd.stop()

    def wait(self) -> None:
        sd.wait()

    @staticmethod
    def _decode_to_pcm(mp3_bytes: bytes) -> np.ndarray:
        proc = subprocess.Popen(
            [_FFMPEG_PATH, "-i", "pipe:0", "-f", "wav",
             "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        wav_bytes, _ = proc.communicate(input=mp3_bytes)

        fmt_start = wav_bytes.find(b"fmt ")
        if fmt_start < 0:
            raise RuntimeError("Could not find fmt chunk")
        data_start = wav_bytes.find(b"data")
        if data_start < 0:
            raise RuntimeError("Could not find data chunk")

        fmt_size = struct.unpack_from("<I", wav_bytes, fmt_start + 4)[0]
        bits_per_sample = struct.unpack_from("<H", wav_bytes, fmt_start + 22)[0]
        data_size = struct.unpack_from("<I", wav_bytes, data_start + 4)[0]
        raw = wav_bytes[data_start + 8 : data_start + 8 + data_size]

        if bits_per_sample == 16:
            return np.frombuffer(raw, dtype=np.int16)
        elif bits_per_sample == 8:
            return (np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128) * 256
        else:
            return np.frombuffer(raw, dtype=np.float32).astype(np.int16)
