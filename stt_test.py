from microphone import Microphone
from VAD import VoiceActivityDetector
from stt import SpeechToText

vad = VoiceActivityDetector()
stt = SpeechToText(model_size="tiny")

mic = Microphone()


def on_audio(chunk):
    segment, _ = vad.process(chunk)

    if segment is not None:
        print("Speech detected")

        text = stt.transcribe(segment)

        print(f"YOU SAID: {text}")


print("Speak...")
print("Press Enter to stop")

mic.start(on_audio)

input()

mic.stop()