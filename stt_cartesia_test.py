import asyncio
from audio_device import LocalAudioDevice
from VAD import VoiceActivityDetector
from stt_cartesia import CartesiaSTT


async def main():
    vad = VoiceActivityDetector()
    stt = CartesiaSTT()
    device = LocalAudioDevice()

    async def on_audio(chunk):
        segment, _ = vad.process(chunk)
        if segment is not None:
            print("Speech detected, transcribing...", flush=True)
            text = await stt.transcribe_async(segment)
            print(f"YOU SAID: {text}", flush=True)

    await device.start(on_audio)
    print("Speak into your microphone...", flush=True)
    print("Press Ctrl+C to stop", flush=True)

    try:
        while True:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    finally:
        await device.close()
        await stt.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
