# 08 · Camera, microphone, speech (`frontend/src/lib/media.ts`, `voice.ts`, `public/pcm-worklet.js`)

**One idea:** the browser can see, hear and speak, but only over HTTPS on a phone.

## HTTPS
`getUserMedia` only exists in a secure context: `https://` or `localhost`. On the phone, open the
`https://...trycloudflare.com` link from `cloudflared tunnel --url http://localhost:8000`.
Over plain http, `navigator.mediaDevices` is `undefined`; the app says so.

## Camera + mic: one stream
`openCameraAndMic()` asks once for both (one permission prompt), back camera preferred
(`facingMode: environment`). `captureFrame()` draws the current video picture onto a canvas,
scales to ≤960 px wide, and makes a JPEG `Blob` (~80 KB) for ask/check.

## Mic → 24 kHz PCM (the AudioWorklet)
Phones record at 44.1 or 48 kHz as floats (-1..1). Meta wants 16-bit integers at 24 kHz.
`pcm-worklet.js` runs on the audio thread (no stutter) and for every input block:
1. **resamples**: walks the input in steps of `48000/24000 = 2`, blending neighbours (linear);
2. **converts**: float × 32767 → Int16;
3. **chunks**: every 1,920 samples (80 ms) posts 3,840 bytes to the page, which sends it on the socket.
It only records between `'start'` and `'stop'` messages: that's the hold-to-talk button.

## Hold to talk
Pointer events (`onPointerDown/Up/Cancel`) cover finger, mouse and pen. `setPointerCapture` keeps
the "up" event even if the finger slides off the button. Down: stop speaking, `{"type":"start"}`;
up: flush audio, `{"type":"stop"}` → server returns the final text → `/api/coach/ask` with a frame.

## Speech out
`speechSynthesis.speak(new SpeechSynthesisUtterance(text))`: free, instant, offline. Voices load
late, so we pick one on `voiceschanged` (Indian English if present). `cancel()` before each new line
so the coach never talks over itself, and when the junior presses talk.

## Wake lock
`navigator.wakeLock.request('screen')` keeps the screen on in the chest mount. The browser drops it
when the tab is hidden, so we re-request on `visibilitychange`.
