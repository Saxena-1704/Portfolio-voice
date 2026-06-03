# Voice Agent — Call Handling System

A modular, async-first voice agent with VAD, barge-in, and a state machine. Built to be telephony-ready — swap one class when you're ready to connect to phone lines.

---

## File-by-File Purpose

### Core Modules

| File | What it does |
|------|-------------|
| `microphone.py` | Captures audio from your mic via sounddevice. *Legacy — replaced by `audio_device.py`* |
| `speaker.py` | Plays audio through your speakers via ffmpeg + sounddevice. *Legacy — replaced by `audio_device.py`* |
| `VAD.py` | **Voice Activity Detection.** Uses Silero VAD to detect when a person is speaking. Feeds audio chunks in, returns full speech segments out. Also flags when speech *just started* (critical for barge-in). |
| `stt.py` | **Speech-to-Text.** Wraps faster-whisper. Turns audio segments into text. |
| `llm.py` | **Language Model.** Calls Groq's API (LLaMA) to generate responses. Async-native. |
| `tts.py` | **Text-to-Speech.** Uses edge-tts (Microsoft's neural voices). Streams raw PCM audio chunks so playback can start before synthesis finishes — and be interrupted mid-word. |
| `audio_device.py` | **Audio I/O abstraction.** `AudioDevice` is the abstract base class. `LocalAudioDevice` implements it with sounddevice for laptop mic/speaker. When you add telephony, write a new class (e.g. `WebRTCAudioDevice`) and swap it in — nothing else changes. |
| `conversation.py` | **Conversation history.** Tracks user/assistant turns with timestamps. Builds the message list sent to the LLM. |
| `state_machine.py` | **Call state machine.** 5 states, 7 events. Invalid transitions are silently ignored. |
| `event_bus.py` | **Async pub/sub.** Lets components broadcast events without knowing about each other. |
| `agent.py` | **The conductor.** Owns all components, runs the state machine, processes speech segments from a queue, handles barge-in. Start here. |

### Test / Legacy Files

| File | Purpose |
|------|---------|
| `VAD_test.py` | Standalone test — speaks when it detects speech |
| `stt_test.py` | Mic → VAD → STT — prints what you said |
| `mic_test.py` | Quick mic check — prints chunk sizes |
| `full_pipeline_test.py` | Legacy sync pipeline (mic→VAD→STT→LLM→TTS→speaker). Replaced by `agent.py` |
| `.env` | Holds `GROQ_API_KEY` |
| `requirements.txt` | Python dependencies |

---

## State Machine

```
         ┌──────────────────────────────────────────┐
         │              STATES                       │
         │                                          │
         │   IDLE ──▶ LISTENING ──▶ PROCESSING      │
         │    ▲                       │              │
         │    │              ┌────────▼────────┐     │
         │    │              │    SPEAKING     │     │
         │    │              └──┬──────────┬───┘     │
         │    │                 │          │         │
         │    │          ┌──────▼──┐  ┌────▼──────┐ │
         │    │          │INTERRUPT│  │PLAYBACK_END│ │
         │    │          │  ED     │  │           │ │
         │    │          └──┬──────┘  └───────────┘ │
         │    │             │                       │
         │    └─────── CALL_END ────────────────────┘
         └──────────────────────────────────────────┘
```

| State | What happens |
|-------|-------------|
| **IDLE** | Waiting to start |
| **LISTENING** | Mic is live, VAD is watching for speech |
| **PROCESSING** | STT is transcribing + LLM is generating a response |
| **SPEAKING** | TTS audio is playing through the speaker |
| **INTERRUPTED** | User spoke during playback — TTS was stopped |

---

## Full Workflow

```
YOU SPEAK ──▶ MIC ──▶ VAD ──▶ STT ──▶ LLM ──▶ TTS ──▶ SPEAKER ──▶ YOU HEAR
                         │                               ▲
                         └── (runs continuously) ─────────┘
                                  (barge-in detection)
```

### Normal call flow

1. **`agent.py`** starts → audio device begins streaming mic input
2. State machine moves `IDLE → LISTENING`
3. Each audio chunk is fed to **VAD** — it accumulates samples until it detects a complete speech segment
4. When speech ends, VAD returns the full audio segment
5. State machine: `LISTENING → PROCESSING`
6. Segment goes into an async **queue**
7. The **processing loop** picks it up:
   - **STT** transcribes it to text
   - **ConversationManager** adds the user turn
   - **LLM** generates a response
   - **ConversationManager** adds the assistant turn
8. State machine: `PROCESSING → SPEAKING`
9. **TTS** streams PCM chunks — **audio_device** plays them as they arrive
10. State machine: `SPEAKING → LISTENING`
11. Back to step 3

### Barge-in (interruption) flow

1. Agent is in **SPEAKING**, TTS playing
2. User starts speaking
3. Next audio chunk → **VAD** detects speech just started → returns `started=True`
4. State machine: `SPEAKING → INTERRUPTED`
5. **TTS playback is stopped immediately** — user hears silence
6. VAD keeps accumulating the user's speech
7. User stops speaking → VAD returns the full segment
8. State machine: `INTERRUPTED → PROCESSING`
9. Segment goes into the queue
10. Processing loop picks it up — normal flow continues

If the user speaks while the agent is still in **PROCESSING** (before TTS starts), the speech gets queued and handled right after the current response finishes.

---

## Adding Telephony

The entire audio layer is behind the `AudioDevice` abstract class:

```python
class AudioDevice(ABC):
    async def start(self, on_audio): ...     # receive mic chunks
    async def play(self, stream): ...        # play TTS stream
    async def stop_playback(self): ...       # stop immediately
    async def close(self): ...               # cleanup
```

To connect to a phone line:

1. Write a new class (e.g. `TwilioMediaStreamDevice`) that implements these four methods using WebRTC or a telephony API
2. Pass it to `VoiceAgentController(audio_device=my_device)`
3. Everything else — VAD, STT, LLM, TTS, state machine, barge-in — works unchanged
