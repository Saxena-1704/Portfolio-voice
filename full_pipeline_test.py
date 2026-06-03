"""Quick integration test for the voice agent pipeline.

Runs the agent for a single turn then exits.
"""
import asyncio
from agent import VoiceAgentController


async def test_single_turn():
    controller = VoiceAgentController()
    await controller.audio_device.start(controller._on_audio_chunk)
    controller._sm.transition(state_machine.CallEvent.CALL_START)

    print("Say something (recording for 5s)...")
    await asyncio.sleep(5)

    await controller.audio_device.close()
    print("Done.")


if __name__ == "__main__":
    import state_machine
    asyncio.run(test_single_turn())
