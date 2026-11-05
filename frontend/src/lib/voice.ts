// Push-to-talk: hold the button, speak, release -> the words come back as text.
//   mic -> AudioWorklet (24 kHz PCM) -> WebSocket /ws/asr -> our server -> Meta -> text
// Learn note: docs/learn/08-browser-media.md

export type VoiceEvents = {
  onPartial: (text: string) => void
  onFinal: (text: string) => void
  onError: (message: string) => void
}

export class PushToTalk {
  private ctx: AudioContext | null = null
  private node: AudioWorkletNode | null = null
  private ws: WebSocket | null = null
  private events: VoiceEvents

  constructor(events: VoiceEvents) { this.events = events }

  /** Call once per session, after a tap (browsers start audio only after a user gesture). */
  async connect(stream: MediaStream) {
    this.ctx = new AudioContext()
    await this.ctx.audioWorklet.addModule('/pcm-worklet.js')
    const source = this.ctx.createMediaStreamSource(stream)
    this.node = new AudioWorkletNode(this.ctx, 'pcm-worklet')
    source.connect(this.node)               // not connected to speakers: no echo
    this.node.port.onmessage = (e) => {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(e.data as ArrayBuffer)
    }
    await this.openSocket()
  }

  private openSocket(): Promise<void> {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/asr`)
    ws.binaryType = 'arraybuffer'
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data as string) as { type: string; text: string }
      if (msg.type === 'partial') this.events.onPartial(msg.text)
      else if (msg.type === 'final') this.events.onFinal(msg.text)
      else if (msg.type === 'error') this.events.onError(msg.text)
    }
    // A socket that dies mid-utterance must say so in words, never leave "Thinking…" stuck.
    ws.onclose = () => { if (this.ws === ws) this.events.onError('Voice connection lost. Ask again?') }
    this.ws = ws
    return new Promise((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.onerror = () => reject(new Error('Voice connection failed'))
    })
  }

  async start() {
    if (this.ws?.readyState !== WebSocket.OPEN) await this.openSocket()   // reconnect after a drop
    await this.ctx?.resume()
    this.ws!.send(JSON.stringify({ type: 'start' }))
    this.node?.port.postMessage('start')
  }

  stop() {
    this.node?.port.postMessage('stop')
    // Give the worklet a moment to flush its last chunk before ending the stream.
    setTimeout(() => this.ws?.readyState === WebSocket.OPEN && this.ws.send(JSON.stringify({ type: 'stop' })), 120)
  }

  close() {
    const ws = this.ws
    this.ws = null // detach first: our own close is expected, not an error
    ws?.close()
    this.node?.disconnect()
    this.ctx?.close().catch(() => {})
  }
}
