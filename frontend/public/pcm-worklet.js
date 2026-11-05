// Runs on the browser's audio thread (AudioWorklet).
// In:  the mic at the device's rate (often 44.1 or 48 kHz), float samples -1..1.
// Out: 16-bit mono PCM at 24 kHz, in 80 ms chunks (1920 samples = 3840 bytes),
//      the format Meta's realtime speech model expects ("PCM_24KHZ").
const TARGET_RATE = 24000
const CHUNK = 1920

class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / TARGET_RATE   // sampleRate: a global inside worklets
    this.pos = 0                            // fractional read position for resampling
    this.out = new Int16Array(CHUNK)
    this.n = 0
    this.on = false
    this.port.onmessage = (e) => {
      this.on = e.data === 'start'
      if (!this.on && this.n > 0) this.flush()   // send the tail when the button is released
    }
  }

  flush() {
    this.port.postMessage(this.out.slice(0, this.n).buffer)
    this.n = 0
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0]
    if (!this.on || !input) return true
    // Linear resampling: step through the input at `ratio`, blend the two neighbours.
    while (this.pos < input.length - 1) {
      const i = Math.floor(this.pos)
      const frac = this.pos - i
      // Non-integer ratios (44.1 kHz) can carry pos below 0 into a block:
      // repeat the first sample instead of reading input[-1] (NaN, heard as a click).
      const s0 = i < 0 ? input[0] : input[i]
      const s = s0 * (1 - frac) + input[i + 1] * frac
      this.out[this.n++] = Math.max(-1, Math.min(1, s)) * 0x7fff
      if (this.n === CHUNK) this.flush()
      this.pos += this.ratio
    }
    this.pos -= input.length                 // carry the remainder into the next block
    return true
  }
}

registerProcessor('pcm-worklet', PcmWorklet)
