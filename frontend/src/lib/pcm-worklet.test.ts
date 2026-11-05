// The resampler in public/pcm-worklet.js, run in Node with stubbed worklet globals:
// a known sine in, 24 kHz Int16 chunks out.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import { describe, expect, it } from 'vitest'

const SRC = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../../public/pcm-worklet.js'), 'utf8')

function loadWorklet(sampleRate: number) {
  let Klass: new () => any
  const sandbox: Record<string, unknown> = {
    sampleRate,
    AudioWorkletProcessor: class {},
    registerProcessor(_name: string, k: new () => any) { Klass = k },
  }
  vm.createContext(sandbox)
  vm.runInContext(SRC, sandbox)
  const chunks: Int16Array[] = []
  // The constructor reads this.port, so provide it on the prototype before `new`.
  Klass!.prototype.port = { postMessage: (b: ArrayBuffer) => chunks.push(new Int16Array(b.slice(0))), onmessage: null }
  const node = new Klass!()
  const message = (data: string) => node.port.onmessage({ data })
  const feed = (block: Float32Array) => node.process([[block]])
  return { message, feed, chunks }
}

const sineBlock = (rate: number, freq: number, amp: number, start: number, len = 128) => {
  const b = new Float32Array(len)
  for (let i = 0; i < len; i++) b[i] = amp * Math.sin((2 * Math.PI * freq * (start + i)) / rate)
  return b
}

const concat = (chunks: Int16Array[]) => {
  const out = new Int16Array(chunks.reduce((n, c) => n + c.length, 0))
  let o = 0
  for (const c of chunks) { out.set(c, o); o += c.length }
  return out
}

describe('pcm-worklet', () => {
  it('downsamples 48 kHz exactly: 1920-sample chunks, right amplitude, no gaps', () => {
    const RATE = 48000, FREQ = 440, AMP = 0.5
    const { message, feed, chunks } = loadWorklet(RATE)
    message('start')
    const BLOCKS = 200
    for (let b = 0; b < BLOCKS; b++) feed(sineBlock(RATE, FREQ, AMP, b * 128))
    expect(chunks.length).toBe(6) // 200*64 = 12800 samples = 6 full chunks + a tail still inside
    expect(chunks.every((c) => c.length === 1920)).toBe(true)
    message('stop')
    expect(chunks.length).toBe(7)
    expect(chunks[6].length).toBe(1280)

    const out = concat(chunks)
    expect(out.length).toBe(12800)
    const peak = Math.max(...out.map((v) => Math.abs(v)))
    expect(peak / (AMP * 0x7fff)).toBeCloseTo(1, 2) // amplitude within 1%
    for (let n = 0; n < out.length; n++) {
      // ratio is exactly 2, so output n is input sample 2n: compare against the ideal sine.
      const ideal = Math.round(AMP * Math.sin((2 * Math.PI * FREQ * 2 * n) / RATE) * 0x7fff)
      expect(Math.abs(out[n] - ideal)).toBeLessThanOrEqual(2)
    }
  })

  it('resamples 44.1 kHz smoothly across block boundaries', () => {
    const RATE = 44100, FREQ = 440, AMP = 0.5, RATIO = RATE / 24000
    const { message, feed, chunks } = loadWorklet(RATE)
    message('start')
    const N = 200 * 128
    for (let b = 0; b < 200; b++) feed(sineBlock(RATE, FREQ, AMP, b * 128))
    message('stop')
    const out = concat(chunks)
    expect(Math.abs(out.length - N / RATIO)).toBeLessThanOrEqual(4)
    // Output n lands within one input sample of time n*RATIO: the sine there is the bound.
    let sum = 0, max = 0
    for (let n = 0; n < out.length; n++) {
      const ideal = AMP * Math.sin((2 * Math.PI * FREQ * n * RATIO) / RATE) * 0x7fff
      const err = Math.abs(out[n] - ideal)
      sum += err
      max = Math.max(max, err)
    }
    expect(max).toBeLessThan(1500) // <5% of full scale at the steepest slope
    expect(sum / out.length).toBeLessThan(400)
  })

  it('only records between start and stop, and flushes the tail', () => {
    const { message, feed, chunks } = loadWorklet(48000)
    feed(sineBlock(48000, 440, 0.5, 0)) // before start: ignored
    expect(chunks.length).toBe(0)
    message('start')
    feed(sineBlock(48000, 440, 0.5, 0))
    feed(sineBlock(48000, 440, 0.5, 128))
    message('stop') // 128 output samples: too few for a chunk, flushed as a tail
    expect(chunks.length).toBe(1)
    expect(chunks[0].length).toBe(128)
    feed(sineBlock(48000, 440, 0.5, 256)) // after stop: ignored
    expect(chunks.length).toBe(1)
  })
})
