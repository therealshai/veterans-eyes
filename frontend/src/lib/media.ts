// Camera, frames, speech out, wake lock. All browser APIs; all need HTTPS on a phone
// (localhost is fine on the laptop). Learn note: docs/learn/08-browser-media.md

/** One stream for the whole session: back camera + mic. Asking once means one permission prompt. */
export async function openCameraAndMic(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Camera needs HTTPS. Open the https:// tunnel link, not http://')
  }
  return navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
}

/** The current video picture as a JPEG, at most 960 px wide (what the models need, fast to upload). */
export function captureFrame(video: HTMLVideoElement, maxWidth = 960): Promise<Blob> {
  const w = video.videoWidth, h = video.videoHeight
  if (!w || !h) return Promise.reject(new Error('The camera is not ready yet'))
  const scale = Math.min(1, maxWidth / w)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * scale)
  canvas.height = Math.round(h * scale)
  canvas.getContext('2d')!.drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not capture a frame'))), 'image/jpeg', 0.82))
}

// ── Speech out ──────────────────────────────────────────────────────────────
let voice: SpeechSynthesisVoice | null = null
function pickVoice() {
  const voices = speechSynthesis.getVoices()
  voice = voices.find((v) => v.lang === 'en-IN') ?? voices.find((v) => v.lang.startsWith('en')) ?? null
}
if (typeof speechSynthesis !== 'undefined') {
  pickVoice()
  speechSynthesis.addEventListener?.('voiceschanged', pickVoice)   // voices load late
}

/** Speak text, cutting off anything still being said. Resolves when done. */
export function speak(text: string): Promise<void> {
  if (typeof speechSynthesis === 'undefined' || !text.trim()) return Promise.resolve()
  speechSynthesis.cancel()
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text)
    if (voice) u.voice = voice
    u.rate = 1
    u.onend = () => resolve()
    u.onerror = () => resolve()
    speechSynthesis.speak(u)
  })
}

/** iOS Safari only lets a page speak if speech first starts inside a tap.
 *  Call this synchronously in the tap handler (before any await); later speak() calls then work. */
export function unlockSpeech() {
  if (typeof speechSynthesis === 'undefined') return
  try { speechSynthesis.speak(new SpeechSynthesisUtterance(' ')) } catch { /* not supported */ }
}

export const stopSpeaking = () => { if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel() }

// ── Screen stays on (phone in a chest mount) ───────────────────────────────
type WakeLock = { release(): Promise<void> }
export async function keepScreenOn(): Promise<() => void> {
  const nav = navigator as Navigator & { wakeLock?: { request(t: 'screen'): Promise<WakeLock> } }
  if (!nav.wakeLock) return () => {}
  let lock: WakeLock | null = null
  const acquire = async () => { try { lock = await nav.wakeLock!.request('screen') } catch { /* denied */ } }
  const onVisible = () => { if (document.visibilityState === 'visible') acquire() }  // released when hidden
  await acquire()
  document.addEventListener('visibilitychange', onVisible)
  return () => { document.removeEventListener('visibilitychange', onVisible); lock?.release().catch(() => {}) }
}
