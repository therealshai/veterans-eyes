# 05 · Voice relay (`backend/live/asr_relay.py`)

**One idea:** the phone never talks to Meta directly; our server passes audio through, holding the key.

```
phone --(WS /ws/asr)--> FastAPI --(WS)--> Meta realtime ASR
      <-- partial/final text --        <-- transcript events
```

## Protocol with the phone
| Phone sends | Meaning |
|---|---|
| `{"type":"start"}` | talk button pressed: open a Meta stream |
| binary messages | 16-bit mono PCM, 24 kHz, ~80 ms each |
| `{"type":"stop"}` | button released: end the stream |

The server answers `{"type":"partial","text":...}`, then `{"type":"final","text":...}`, or `{"type":"error"}`.

## The queue trick
Opening Meta's socket takes ~1.5 s (Oct 27). On "start" we create an `asyncio.Queue` and start
`_meta_stream` as a task; audio arriving meanwhile waits in the queue. The junior is still talking
during that 1.5 s, so they never feel it. `None` in the queue means "end of speech" → `endStream`.

## async, in one paragraph
`async def` + `await` lets one thread juggle many waits: receiving from the phone and sending to
Meta happen "at the same time" without threads. `asyncio.create_task` starts something that runs
alongside; `await queue.get()` pauses only that task until data arrives.

## Failure handling
Any Meta error is sent to the phone as `{"type":"error"}`; the app then offers typing instead.
A 60 s timeout stops a stuck stream. Disconnects close everything in `finally`.

**Check yourself:** what would break if the phone called Meta's WebSocket itself?
