from microphone import Microphone
from VAD import VoiceActivityDetector

vad = VoiceActivityDetector()

def on_audio(chunk):
    segment, _ = vad.process(chunk)

    if segment is not None:
        duration = len(segment) / 16000

        print(
            f"[SPEECH DETECTED] "
            f"duration={duration:.2f}s "
            f"samples={len(segment)}"
        )

mic = Microphone()

print("Speak...")
print("Press Enter to stop")

mic.start(on_audio)

input()

mic.stop()