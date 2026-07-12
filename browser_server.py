import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from agent import VoiceAgentController
from browser_device import BrowserAudioDevice


app = FastAPI(title="Portfolio Voice Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    return FileResponse("static/classic.html")


@app.websocket("/ws/audio")
async def audio_stream(ws: WebSocket):
    await ws.accept()
    device = None
    agent = None
    agent_task = None

    try:
        device = BrowserAudioDevice(ws)
        agent = VoiceAgentController(audio_device=device)
        agent_task = asyncio.create_task(agent.run())
        await device.wait_for_call_end()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        if agent:
            await agent.stop()
        if agent_task:
            try:
                await agent_task
            except Exception:
                pass
        if device:
            await device.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("browser_server:app", host="0.0.0.0", port=8765, reload=True)
