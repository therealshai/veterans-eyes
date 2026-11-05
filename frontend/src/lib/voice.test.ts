import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PushToTalk } from './voice'

class FakeSocket {
  static OPEN = 1
  readyState = 1
  sent: Array<string | ArrayBuffer> = []
  onmessage: ((e: { data: string }) => void) | null = null
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  url: string
  constructor(url: string) { this.url = url; setTimeout(() => this.onopen?.(), 0) }
  send(d: string | ArrayBuffer) { this.sent.push(d) }
  close() { this.readyState = 3; this.onclose?.() }
  die() { this.readyState = 3; this.onclose?.() } // network drop, no clean close
  receive(text: string) { this.onmessage?.({ data: text }) }
}

const sockets: FakeSocket[] = []
beforeEach(() => {
  sockets.length = 0
  vi.stubGlobal('WebSocket', class extends FakeSocket {
    constructor(url: string) { super(url); sockets.push(this) }
  })
  vi.stubGlobal('location', { protocol: 'http:', host: 'x' })
  vi.stubGlobal('AudioContext', class {
    audioWorklet = { addModule: async () => {} }
    createMediaStreamSource = () => ({ connect: () => {} })
    resume = async () => {}
    close = async () => {}
  })
  vi.stubGlobal('AudioWorkletNode', class {
    port = { postMessage: () => {}, onmessage: null }
    disconnect() {}
  })
})

const events = () => {
  const seen: Array<[string, string]> = []
  return { seen, events: {
    onPartial: (t: string) => seen.push(['partial', t]),
    onFinal: (t: string) => seen.push(['final', t]),
    onError: (t: string) => seen.push(['error', t]),
  } }
}

describe('PushToTalk', () => {
  it('a socket that dies mid-utterance reports an error in words', async () => {
    const s = events()
    const ptt = new PushToTalk(s.events)
    await ptt.connect({} as MediaStream)
    await ptt.start()
    sockets[0].die()
    expect(s.seen).toContainEqual(['error', 'Voice connection lost. Ask again?'])
  })

  it('our own close() is not reported as an error', async () => {
    const s = events()
    const ptt = new PushToTalk(s.events)
    await ptt.connect({} as MediaStream)
    ptt.close()
    expect(s.seen).toEqual([])
  })

  it('start() reconnects after a drop', async () => {
    const s = events()
    const ptt = new PushToTalk(s.events)
    await ptt.connect({} as MediaStream)
    sockets[0].die()
    await ptt.start() // opens a second socket instead of failing
    expect(sockets.length).toBe(2)
    expect(sockets[1].sent[0]).toBe(JSON.stringify({ type: 'start' }))
    ptt.close()
  })
})
