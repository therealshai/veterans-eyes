"""
Voice relay: the phone streams microphone audio to us, we stream it to Meta's
realtime speech model, and send the words back to the phone.

    phone --(WebSocket /ws/asr)--> FastAPI --(WebSocket)--> Meta realtime ASR
          <-- {"type":"partial"|"final","text"} --       <-- transcript events

Why a relay instead of the phone calling Meta: the API key must never reach the browser.

Protocol with the phone (one connection per coaching session, many questions):
    {"type":"start"}         the talk button went down: open a Meta stream
    <binary>                 audio: 16-bit mono PCM at 24 kHz, ~80 ms per message
    {"type":"stop"}          the button came up: finish the stream, wait for the final text
The Meta socket takes ~1.5 s to open, so audio that arrives meanwhile waits in a
queue: the junior is still talking during that time, so they never feel it.
Learn note: docs/learn/05-voice-relay.md
"""
import asyncio
import json
import ssl
import uuid

import certifi
import websockets
from fastapi import WebSocket, WebSocketDisconnect

from backend.config import API_KEY, ASR_MODEL, ASR_URL

_ssl = ssl.create_default_context(cafile=certifi.where())


async def _meta_stream(audio: asyncio.Queue, to_phone) -> None:
    """One utterance: audio from the queue (None = end) -> Meta -> partial/final to the phone."""
    uri = f"{ASR_URL}?sessionId=coach-{uuid.uuid4()}"
    async with websockets.connect(uri, open_timeout=15, ssl=_ssl) as ws:
        await ws.send(json.dumps({
            "authorization": {"accessToken": f"Bearer {API_KEY}"},
            "audioEncoding": "PCM_24KHZ", "model": ASR_MODEL,
            "mode": "PUSH_TO_TALK", "partialMode": "CUMULATIVE", "emitAudioProgress": False,
        }))
        handshake = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if "sessionId" not in handshake:
            raise RuntimeError(f"ASR handshake failed: {handshake}")

        async def pump_audio():
            while (chunk := await audio.get()) is not None:
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "endStream"}))

        sender = asyncio.create_task(pump_audio())
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                if event.get("type") == "error":
                    raise RuntimeError(event.get("message", str(event)))
                if event.get("type") != "transcript":
                    continue
                if event.get("final"):
                    await to_phone({"type": "final", "text": event.get("transcript", "")})
                    return
                await to_phone({"type": "partial", "text": event.get("transcript", "")})
            await to_phone({"type": "final", "text": ""})
        finally:
            sender.cancel()


async def handle(phone: WebSocket) -> None:
    await phone.accept()
    audio: asyncio.Queue | None = None
    stream: asyncio.Task | None = None

    async def to_phone(msg: dict) -> None:
        try:
            await phone.send_text(json.dumps(msg))
        except Exception:
            pass                                    # phone gone: nothing to tell

    async def run_stream(q: asyncio.Queue) -> None:
        try:
            await asyncio.wait_for(_meta_stream(q, to_phone), timeout=60)
        except Exception as e:
            await to_phone({"type": "error", "text": f"Speech service: {e}"})

    try:
        while True:
            msg = await phone.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if audio is not None:
                    audio.put_nowait(msg["bytes"])
                continue
            kind = json.loads(msg.get("text") or "{}").get("type")
            if kind == "start":
                if audio is not None:
                    audio.put_nowait(None)             # close a stream left open
                audio = asyncio.Queue()
                stream = asyncio.create_task(run_stream(audio))
            elif kind == "stop" and audio is not None:
                audio.put_nowait(None)
                audio = None
    except WebSocketDisconnect:
        pass
    finally:
        if audio is not None:
            audio.put_nowait(None)
        if stream is not None and not stream.done():
            stream.cancel()
