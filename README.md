# Voice Agent — Call Handling System

A modular, async-first voice agent with **Twilio telephony**, **Cartesia STT/TTS**, **Silero VAD**, **Groq LLM**, and **barge-in** support. The audio layer is abstracted behind an `AudioDevice` interface — the same agent code powers both local mic/speaker and phone calls.

---

## Architecture

```
                     ┌──────────────────────────────────────────────┐
                     │              Twilio Server                   │
                     │  (FastAPI, port 8765)                        │
                     │                                              │
  Twilio Voice ─────▶│  POST /incoming_call  (TwiML)              │
  (PSTN / SIP)       │  POST /make_call      (outbound REST)      │
                     │  WS  /media-stream    (µ-law ↔ PCM audio)  │
                     └──────────────┬───────────────────────────────┘
                                    │ TwilioMediaStreamDevice
                                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                    VoiceAgentController (agent.py)                 │
│                                                                   │
│  AudioDevice ──▶ VAD ──▶ [segment queue] ──▶ CartesiaSTT         │
│      ▲                                          │                 │
│      │                                    ConversationManager     │
│      │                                          │                 │
│      │                                         LLM (Groq)         │
│      │                                          │                 │
│      │                                    CartesiaTTS             │
│      │                                          │                 │
│      └────────────── play() ◀───────────────────┘                 │
│                                                                   │
│  StateMachine: IDLE → LISTENING → PROCESSING → SPEAKING → ...    │
│  Barge-in: SPEAKING → INTERRUPTED on VAD speech start            │
└───────────────────────────────────────────────────────────────────┘
```

---

## File-by-File Purpose

### Core Modules

| File | What it does |
|------|-------------|
| `agent.py` | **The conductor.** Owns all components, runs the state machine, processes speech segments from an async queue, handles barge-in. Accepts any `AudioDevice` implementation. |
| `audio_device.py` | **Audio I/O abstraction.** `AudioDevice` (ABC) with `start()`, `play()`, `stop_playback()`, `close()`. `LocalAudioDevice` implements it via `sounddevice` for laptop mic/speaker. |
| `twilio_device.py` | **Twilio audio device.** Implements `AudioDevice` over Twilio WebSocket media streams. Converts µ-law (8 kHz) ↔ linear PCM (16 kHz). |
| `twilio_server.py` | **FastAPI server** (port 8765). Endpoints: `POST /twilio/incoming_call` (TwiML), `POST /twilio/make_call` (outbound), `WS /twilio/media-stream` (real-time audio). Creates one `VoiceAgentController` per call. |
| `stt_cartesia.py` | **Speech-to-Text** via Cartesia WebSocket API (model `ink-2`). Sends PCM chunks, receives streaming transcripts. |
| `tts_cartesia.py` | **Text-to-Speech** via Cartesia WebSocket API (model `sonic-3.5`). Supports streaming token→audio — LLM tokens are pushed incrementally so audio starts before the full response is ready. |
| `VAD.py` | **Voice Activity Detection** using Silero VAD. Returns full speech segments and a `started` flag (critical for barge-in). |
| `llm.py` | **Language Model.** Calls Groq's API (LLaMA) with async streaming support. |
| `conversation.py` | **Conversation history.** Tracks user/assistant turns, builds the message list sent to the LLM with a system prompt. |
| `state_machine.py` | **Call state machine.** 5 states (`IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `INTERRUPTED`), 7 events. Invalid transitions silently ignored. |
| `event_bus.py` | **Async pub/sub.** Defined but currently unused by `VoiceAgentController`. |
| `make_call.py` | Standalone script to initiate an outbound Twilio call via the REST API. |

### Test / Debug Files

| File | Purpose |
|------|---------|
| `VAD_test.py` | Standalone VAD test — prints speech segment durations |
| `stt_test.py` | Mic → VAD → Whisper STT — prints transcriptions (legacy) |
| `stt_cartesia_test.py` | Mic → VAD → Cartesia STT — prints transcriptions |
| `mic_test.py` | Quick mic check — prints chunk sizes |
| `full_pipeline_test.py` | Legacy sync pipeline (mic→VAD→STT→LLM→TTS→speaker) |

### Legacy Files (no longer used by agent.py)

| File | Replaced by |
|------|-------------|
| `microphone.py` | `LocalAudioDevice` in `audio_device.py` |
| `speaker.py` | `LocalAudioDevice` in `audio_device.py` |
| `stt.py` | `CartesiaSTT` in `stt_cartesia.py` |
| `tts.py` | `CartesiaTTS` in `tts_cartesia.py` |

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
| **IDLE** | Waiting for call to start |
| **LISTENING** | Audio device is live, VAD is watching for speech |
| **PROCESSING** | STT transcribing + LLM generating. Self-loop allows queued segments. |
| **SPEAKING** | TTS audio is playing through the audio device |
| **INTERRUPTED** | User spoke during playback — TTS was stopped, VAD accumulates remainder |

### Transitions

| From | Event | To |
|------|-------|----|
| IDLE | `CALL_START` | LISTENING |
| LISTENING | `SPEECH_END` | PROCESSING |
| LISTENING | `CALL_END` | IDLE |
| PROCESSING | `SPEECH_END` | PROCESSING |
| PROCESSING | `RESPONSE_READY` | SPEAKING |
| PROCESSING | `ERROR` | LISTENING |
| PROCESSING | `CALL_END` | IDLE |
| SPEAKING | `PLAYBACK_END` | LISTENING |
| SPEAKING | `INTERRUPT` | INTERRUPTED |
| SPEAKING | `CALL_END` | IDLE |
| INTERRUPTED | `SPEECH_END` | PROCESSING |
| INTERRUPTED | `CALL_END` | IDLE |

---

## Call Flow

### Normal call

1. Agent starts → audio device streams input chunks to VAD
2. State: `IDLE → LISTENING`
3. VAD accumulates chunks, detects speech start → start flag set
4. User stops speaking → VAD returns the complete audio segment
5. State: `LISTENING → PROCESSING`
6. Segment goes into an async queue
7. Processing loop picks it up:
   - **CartesiaSTT** transcribes to text
   - **ConversationManager** adds the user turn
   - **LLM** generates a streaming response
   - **CartesiaTTS** receives tokens as they arrive — audio starts before LLM finishes
8. State: `PROCESSING → SPEAKING`
9. TTS audio chunks play through the audio device in real-time
10. State: `SPEAKING → LISTENING`
11. Back to step 3

### Barge-in (interruption)

1. Agent is in **SPEAKING**, TTS playing
2. User starts speaking
3. VAD detects speech just started → `started=True` on next chunk
4. State: `SPEAKING → INTERRUPTED`
5. `tts.stop()` called → cancels current Cartesia TTS stream
6. `audio_device.stop_playback()` called → user hears silence
7. VAD keeps accumulating the user's speech
8. User stops → VAD returns the segment
9. State: `INTERRUPTED → PROCESSING`
10. Segment queued → processing continues normally

If the user speaks while still in **PROCESSING**, the speech is queued and handled after the current response finishes.

---

## Setup

### 1. Install dependencies

```
pip install -r requirements.txt
```

Note: `cartesia[websockets]` requires Cartesia API access. `silero-vad` downloads the model on first use. For Twilio, ensure `fastapi`, `uvicorn`, `twilio`, and `python-multipart` are installed.

### 2. Configure `.env`

```
GROQ_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TWILIO_WS_URL=wss://your-ngrok-url.ngrok-free.app/twilio/media-stream
MY_PHONE_NUMBER=+91xxxxxxxxxx
CARTESIA_API_KEY=sk_car_...
```

### 3. (Twilio) Expose the server with ngrok

```
ngrok http 8765
```

Update `TWILIO_WS_URL` in `.env` to match the ngrok `wss://` URL.

---

## Running

### Local mode (laptop mic + speaker)

```
python agent.py
```

Speak into your mic. The agent will listen, think, and respond through your speakers.

### Twilio server (phone calls)

```
python twilio_server.py
```

**Inbound calls:** Configure your Twilio number's webhook to `POST https://<ngrok>/twilio/incoming_call`.

**Outbound calls:** Use the auto-generated endpoint:

```bash
curl -X POST https://<ngrok>/twilio/make_call
```

Or run `python make_call.py` directly.

---

## Key Design Points

- **`AudioDevice` abstraction** — `LocalAudioDevice` for local mic/speaker, `TwilioMediaStreamDevice` for phone calls. Swap by passing a different device to `VoiceAgentController`.
- **Streaming token→audio** — LLM tokens are pushed to Cartesia TTS incrementally via `TextToSpeechStream.push()`, enabling concurrent generation and playback with `asyncio.gather`.
- **Barge-in** — VAD's `started` flag triggers immediate TTS interruption. VAD state is reset before each TTS playback to avoid stale detection.
- **Real-time throttling** — `TwilioMediaStreamDevice.play()` uses `time.monotonic()` drift compensation to stay synchronized with the 16 kHz audio clock.
- **µ-law conversion** — Twilio delivers 8 kHz µ-law audio. `twilio_device.py` handles µ-law ↔ linear PCM conversion and linear interpolation resampling (8↔16 kHz).

---

## Dependencies

| Package | Used for |
|---------|----------|
| `sounddevice` | Local audio I/O (`LocalAudioDevice`) |
| `silero-vad` | Voice Activity Detection |
| `numpy` | Audio data manipulation |
| `groq` | Groq LLM API |
| `cartesia[websockets]` | Cartesia STT + TTS |
| `fastapi` | Twilio web server |
| `uvicorn[standard]` | ASGI server |
| `twilio` | Twilio REST API + TwiML |
| `python-multipart` | FastAPI form parsing |
| `python-dotenv` | `.env` loading |
| `ngrok` | Tunnel for Twilio webhook |

Legacy (no longer used by the agent pipeline): `faster-whisper`, `edge-tts`.
