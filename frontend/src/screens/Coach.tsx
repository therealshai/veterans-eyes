import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, Camera, ChevronLeft, CircleCheck, CircleHelp, Film, Keyboard, Loader2, Mic, ScanSearch, Send, Wrench, X,
} from 'lucide-react'
import { ErrorNote } from '@/components/Shell'
import { DemoBadge } from '@/components/DemoBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { api, fileUrl, type Box, type CheckResult, type Guide } from '@/lib/api'
import { captureFrame, keepScreenOn, openCameraAndMic, speak, stopSpeaking, unlockSpeech } from '@/lib/media'
import { highlightStyle } from '@/lib/highlight'
import { go, href } from '@/lib/router'
import { saveSession, type Session, type SessionEvent } from '@/lib/session'
import { cn } from '@/lib/utils'
import { PushToTalk } from '@/lib/voice'

// followSteps: replaying the guide's own video jumps to each step's moment (realistic test checks)
type Source = { kind: 'camera' } | { kind: 'replay'; url: string; followSteps?: boolean }
type Talk =
  | { state: 'idle' }
  | { state: 'listening'; text: string }
  | { state: 'thinking'; question: string }
  | { state: 'answer'; question: string; answer: string }
  | { state: 'error'; message: string }

/** The junior's phone screen. Learn note: docs/learn/07-frontend.md */
export default function Coach({ id }: { id: string }) {
  const [guide, setGuide] = useState<Guide | null>(null)
  const [error, setError] = useState('')
  const [source, setSource] = useState<Source | null>(null)

  useEffect(() => {
    api.getGuide(id)
      .then(({ guide }) => (guide ? setGuide(guide) : setError('This guide is still processing.')))
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <div className="p-4"><ErrorNote message={error} /></div>
  if (!guide) return <div className="grid min-h-dvh place-items-center text-muted-foreground"><Loader2 className="animate-spin" /></div>
  if (!source) return <SourcePicker guide={guide} onPick={setSource} />
  return <Session guide={guide} source={source} />
}

// ── Before starting: live camera, or a recorded video standing in for it ──────────────

export function SourcePicker({ guide, onPick: pick }: { guide: Guide; onPick: (s: Source) => void }) {
  // Every start is a tap: unlock iOS speech in that same tap, then start the session.
  const onPick = (s: Source) => { unlockSpeech(); pick(s) }
  return (
    <div className="mx-auto grid min-h-dvh max-w-md content-center gap-6 p-4">
      <div>
        <a href={href({ name: 'home' })} className="text-sm text-muted-foreground">← Guides</a>
        <h1 className="mt-3 text-2xl font-semibold leading-tight">{guide.title}</h1>
        <p className="mt-1 text-muted-foreground">{guide.steps.length} steps · {guide.steps.filter((s) => s.critical).length} checks</p>
      </div>
      <Button size="xl" onClick={() => onPick({ kind: 'camera' })}><Camera />Start with camera</Button>
      <div className="grid gap-2">
        <p className="text-sm text-muted-foreground">Replay: a recorded video plays in place of the camera (testing and demo backup).</p>
        <Button size="touch" variant="outline" onClick={() => onPick({ kind: 'replay', url: fileUrl(guide.id, 'video.mp4'), followSteps: true })}>
          <Film />Replay the expert's video
        </Button>
        <label className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-md border px-5 text-base font-medium shadow-xs hover:bg-accent">
          <Film className="size-4" />Replay a video file…
          <input type="file" accept="video/*" className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick({ kind: 'replay', url: URL.createObjectURL(f) }) }} />
        </label>
      </div>
    </div>
  )
}

// ── The session ───────────────────────────────────────────────────────────────────

function Session({ guide, source }: { guide: Guide; source: Source }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const voiceRef = useRef<PushToTalk | null>(null)
  const sessionRef = useRef<Session>({ guideId: guide.id, startedAt: Date.now(), source: source.kind, events: [] })
  const [ready, setReady] = useState(false)
  const [startError, setStartError] = useState('')
  const [index, setIndex] = useState(0)
  const [check, setCheck] = useState<{ state: 'idle' } | { state: 'checking' } | ({ state: 'done' } & CheckResult)>({ state: 'idle' })
  const [passed, setPassed] = useState<Set<number>>(new Set())
  const [talk, setTalk] = useState<Talk>({ state: 'idle' })
  const [typing, setTyping] = useState(false)
  const [typed, setTyped] = useState('')
  const [aspect, setAspect] = useState(16 / 9)
  const [showExpert, setShowExpert] = useState(false)

  const step = guide.steps[index]
  const isLast = index === guide.steps.length - 1
  const needsCheck = step.critical && !passed.has(step.step_no)

  const log = useCallback((e: SessionEvent) => {
    sessionRef.current.events.push(e)
    saveSession(sessionRef.current)
  }, [])

  // ── Start: camera/mic (or video + mic), voice socket, wake lock ──
  useEffect(() => {
    let stream: MediaStream | null = null
    let releaseWake = () => {}
    let cancelled = false
    ;(async () => {
      try {
        const video = videoRef.current!
        if (source.kind === 'camera') {
          stream = await openCameraAndMic()
          video.srcObject = stream
        } else {
          video.src = source.url
          video.loop = false
          stream = await navigator.mediaDevices?.getUserMedia({ audio: true }).catch(() => null) ?? null
        }
        await video.play().catch(() => {})
        releaseWake = await keepScreenOn()
        if (stream && stream.getAudioTracks().length) {
          const voice = new PushToTalk({
            onPartial: (text) => setTalk({ state: 'listening', text }),
            onFinal: (text) => askQuestion(text),
            onError: (message) => setTalk({ state: 'error', message }),
          })
          await voice.connect(stream)
          voiceRef.current = voice
        } else {
          setTyping(true)              // no mic: typing is the way to ask
        }
        if (!cancelled) setReady(true)
      } catch (e) {
        setStartError((e as Error).message)
      }
    })()
    return () => {
      cancelled = true
      stopSpeaking()
      voiceRef.current?.close()
      stream?.getTracks().forEach((t) => t.stop())
      releaseWake()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source])

  // ── Each new step: speak it, log it, clear the last check ──
  useEffect(() => {
    if (!ready) return
    setCheck({ state: 'idle' })
    setShowExpert(false)
    log({ kind: 'step', step: step.step_no, at: Date.now() })
    const video = videoRef.current
    if (source.kind === 'replay' && source.followSteps && video) {
      video.currentTime = step.start_s
      video.play().catch(() => {})
    }
    const warn = step.warnings.length ? ` Careful: ${step.warnings[0]}` : ''
    speak(`Step ${step.step_no}. ${step.instruction}.${warn}`)
  }, [ready, index]) // eslint-disable-line react-hooks/exhaustive-deps

  async function frame(): Promise<Blob | null> {
    try { return await captureFrame(videoRef.current!) } catch { return null }
  }

  async function askQuestion(question: string) {
    const q = question.trim()
    if (!q) { setTalk({ state: 'error', message: "I didn't hear a question. Hold the button while you speak." }); return }
    setTalk({ state: 'thinking', question: q })
    try {
      const r = await api.ask(guide.id, step.step_no, q, await frame())
      setTalk({ state: 'answer', question: q, answer: r.answer })
      log({ kind: 'ask', step: step.step_no, at: Date.now(), question: q, answer: r.answer, seconds: r.seconds })
      speak(r.answer)
    } catch (e) {
      setTalk({ state: 'error', message: (e as Error).message })
    }
  }

  async function runCheck() {
    const image = await frame()
    if (!image) return
    stopSpeaking()
    setCheck({ state: 'checking' })
    speak('Checking.')
    try {
      const r = await api.check(guide.id, step.step_no, image)
      setCheck({ state: 'done', ...r })
      log({ kind: 'check', step: step.step_no, at: Date.now(), verdict: r.verdict, say: r.say, seconds: r.seconds })
      if (r.verdict === 'match') setPassed((p) => new Set(p).add(step.step_no))
      speak(r.verdict === 'match' ? `Matches the expert. ${r.say}` : r.say)
    } catch (e) {
      setCheck({ state: 'idle' })
      setTalk({ state: 'error', message: `Check failed: ${(e as Error).message}` })
    }
  }

  function next() {
    stopSpeaking()
    setTalk({ state: 'idle' })
    if (isLast) {
      sessionRef.current.endedAt = Date.now()
      saveSession(sessionRef.current)
      speak('All steps done. Well done.')
      go({ name: 'summary', id: guide.id })
    } else {
      setIndex((i) => i + 1)
    }
  }

  function skipCheck() {
    log({ kind: 'skip-check', step: step.step_no, at: Date.now() })
    setPassed((p) => new Set(p).add(step.step_no))
  }

  // Hold to talk: pointer events cover mouse, touch and pen in one API.
  const talkDown = (e: React.PointerEvent) => {
    e.preventDefault()
    if (!voiceRef.current) return
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)   // keep receiving "up" if the finger slides off
    stopSpeaking()
    setTalk({ state: 'listening', text: '' })
    voiceRef.current.start().catch((err) => setTalk({ state: 'error', message: err.message }))
  }
  const talkUp = () => {
    if (talk.state !== 'listening') return
    voiceRef.current?.stop()
    setTalk({ state: 'thinking', question: '…' })
  }

  const box = check.state === 'done' ? check.highlight : null

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      {/* Top bar: where am I */}
      <header className="sticky top-0 z-10 border-b bg-background/95 px-3 pt-2 pb-2 backdrop-blur">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="icon" aria-label="End session">
            <a href={href({ name: 'home' })}><X /></a>
          </Button>
          <p className="flex-1 text-sm font-medium tabular-nums">Step {index + 1} of {guide.steps.length}</p>
          <DemoBadge />
          {source.kind === 'replay' && <Badge variant="secondary">Replay</Badge>}
        </div>
        <Progress value={((index + 1) / guide.steps.length) * 100} className="mt-2" />
      </header>

      <div className="mx-auto grid w-full max-w-5xl flex-1 content-start gap-3 p-3 md:grid-cols-[1fr_380px]">
        {/* Camera (or replay) with the highlight from the last check */}
        <div className="relative mx-auto w-full overflow-hidden rounded-xl bg-black" style={{ aspectRatio: aspect, maxHeight: '48dvh' }}>
          <video ref={videoRef} playsInline muted autoPlay className="size-full object-contain"
            onLoadedMetadata={(e) => e.currentTarget.videoWidth && setAspect(e.currentTarget.videoWidth / e.currentTarget.videoHeight)} />
          {box && <Highlight box={box} label={step.highlight_part || step.parts[0]} />}
          {!ready && !startError && <div className="absolute inset-0 grid place-items-center text-white/80"><Loader2 className="animate-spin" /></div>}
          {check.state === 'checking' && (
            <div className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 bg-black/60 py-2 text-sm text-white">
              <Loader2 className="size-4 animate-spin" />Comparing with the expert…
            </div>
          )}
        </div>

        <div className="grid content-start gap-3">
          {startError && <ErrorNote message={startError} />}

          {/* The step */}
          <Card className="gap-3 py-4">
            <div className="flex gap-3 px-4">
              <div className="min-w-0 flex-1">
                <p className="text-xl leading-snug font-semibold">{step.instruction}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {step.critical && <Badge variant={passed.has(step.step_no) ? 'ok' : 'outline'}><ScanSearch />{passed.has(step.step_no) ? 'Checked' : 'Check needed'}</Badge>}
                  {step.tools.map((t) => <Badge key={t} variant="secondary"><Wrench />{t}</Badge>)}
                </div>
              </div>
              {step.keyframe && (
                <button onClick={() => setShowExpert((v) => !v)} className="w-24 shrink-0 text-left" aria-label="Show the expert's photo">
                  <img src={fileUrl(guide.id, step.keyframe)} alt="" className="aspect-video w-full rounded-md object-cover" />
                  <span className="mt-1 block text-xs text-muted-foreground">Expert</span>
                </button>
              )}
            </div>
            {showExpert && step.keyframe && (
              <img src={fileUrl(guide.id, step.keyframe)} alt={`Expert doing step ${step.step_no}`} className="w-full" />
            )}
            {step.warnings.length > 0 && (
              <div className="mx-4 flex gap-2 rounded-md border border-warn bg-warn/10 px-3 py-2 text-base">
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" />
                <p>{step.warnings.join(' ')}</p>
              </div>
            )}
          </Card>

          <Verdict check={check} />
          <TalkPanel talk={talk} />

          {typing && (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); askQuestion(typed); setTyped('') }}>
              <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Type a question" className="h-12" />
              <Button size="icon-touch" type="submit" aria-label="Ask"><Send /></Button>
            </form>
          )}
        </div>
      </div>

      {/* Controls: always in reach of a thumb */}
      <footer className="sticky bottom-0 border-t bg-background/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
        <div className="mx-auto grid max-w-5xl gap-2">
          <div className="flex gap-2">
            <Button size="icon-touch" variant="outline" aria-label="Previous step" disabled={index === 0}
              onClick={() => { stopSpeaking(); setIndex((i) => i - 1) }}><ChevronLeft /></Button>
            {needsCheck ? (
              <Button size="touch" className="flex-1" disabled={!ready || check.state === 'checking'} onClick={runCheck}>
                <ScanSearch />{check.state === 'done' ? 'Check again' : 'Check my work'}
              </Button>
            ) : (
              <Button size="touch" variant={step.critical ? 'ok' : 'default'} className="flex-1" disabled={!ready} onClick={next}>
                <CircleCheck />{isLast ? 'Finish' : 'Done, next step'}
              </Button>
            )}
            <Button size="icon-touch" variant={typing ? 'secondary' : 'outline'} aria-label="Type a question" onClick={() => setTyping((v) => !v)}>
              <Keyboard />
            </Button>
          </div>
          {needsCheck && check.state === 'done' && check.verdict !== 'match' && (
            <button className="h-10 text-sm text-muted-foreground underline underline-offset-4" onClick={skipCheck}>Skip check and continue</button>
          )}
          <Button size="xl" variant={talk.state === 'listening' ? 'destructive' : 'secondary'}
            className="touch-none select-none" disabled={!ready || !voiceRef.current}
            onPointerDown={talkDown} onPointerUp={talkUp} onPointerCancel={talkUp} onContextMenu={(e) => e.preventDefault()}>
            <Mic className="size-6" />{talk.state === 'listening' ? 'Listening… release to ask' : 'Hold to ask'}
          </Button>
        </div>
      </footer>
    </div>
  )
}

/** The part's box, placed in % of the picture so it lines up at any screen size. */
function Highlight({ box, label }: { box: Box; label: string }) {
  const style = highlightStyle(box)
  return (
    <div className="pointer-events-none absolute rounded-sm border-4 border-warn bg-warn/15" style={style}>
      <span className="absolute -top-7 left-0 rounded-sm bg-warn px-1.5 py-0.5 text-xs font-semibold whitespace-nowrap text-warn-foreground">{label}</span>
    </div>
  )
}

function Verdict({ check }: { check: { state: string } & Partial<CheckResult> }) {
  if (check.state !== 'done' || !check.verdict) return null
  const look = {
    match: { icon: <CircleCheck className="size-5 text-ok" />, title: 'Matches the expert', cls: 'border-ok bg-ok/10' },
    fix: { icon: <AlertTriangle className="size-5 text-destructive" />, title: 'Fix this', cls: 'border-destructive bg-destructive/5' },
    unclear: { icon: <CircleHelp className="size-5 text-muted-foreground" />, title: "Can't see clearly", cls: 'border-border bg-muted' },
  }[check.verdict]
  return (
    <div role="status" className={cn('flex gap-3 rounded-lg border px-4 py-3', look.cls)}>
      {look.icon}
      <div><p className="font-semibold">{look.title}</p><p className="text-base">{check.say}</p></div>
    </div>
  )
}

function TalkPanel({ talk }: { talk: Talk }) {
  if (talk.state === 'idle') return null
  if (talk.state === 'error') return <ErrorNote message={talk.message} />
  return (
    <div className="grid gap-2 rounded-lg border bg-card px-4 py-3" aria-live="polite">
      {talk.state === 'listening' && <p className="text-muted-foreground">{talk.text || 'Listening…'}</p>}
      {(talk.state === 'thinking' || talk.state === 'answer') && <p className="text-sm text-muted-foreground">You: {talk.question}</p>}
      {talk.state === 'thinking' && <p className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" />Thinking…</p>}
      {talk.state === 'answer' && <p className="text-base font-medium">{talk.answer}</p>}
    </div>
  )
}
