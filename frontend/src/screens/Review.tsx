import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Loader2, Play } from 'lucide-react'
import { Shell, ErrorNote } from '@/components/Shell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { api, fileUrl, type Guide, type Job, type Step } from '@/lib/api'
import { mmss } from '@/lib/format'
import { href } from '@/lib/router'

/** The senior's desk screen: watch progress, fix what the AI got wrong, publish. */
export default function Review({ id }: { id: string }) {
  const [guide, setGuide] = useState<Guide | null>(null)
  const [job, setJob] = useState<Job>({})
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    const load = () =>
      api.getGuide(id)
        .then(({ guide, job }) => {
          if (!alive) return
          setJob(job); setError('')
          if (job.status === 'processing') { timer = window.setTimeout(load, 2000); return }
          setGuide(guide)
        })
        .catch((e) => alive && setError(e.message))
    load()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [id])

  const updateStep = (no: number, patch: Partial<Step>) => {
    setGuide((g) => g && { ...g, steps: g.steps.map((s) => (s.step_no === no ? { ...s, ...patch } : s)) })
    setDirty(true)
  }

  async function save(publish = false) {
    if (!guide) return
    setSaving(true); setError('')
    try {
      let g = dirty ? await api.saveGuide(guide) : guide
      if (publish) g = await api.publish(g.id)
      setGuide(g); setDirty(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (job.status === 'processing') {
    return (
      <Shell title={job.title || 'New guide'} back={{ name: 'home' }}>
        <Card className="mx-auto max-w-md items-center px-6 py-12 text-center">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="font-medium">{job.progress || 'Processing…'}</p>
          <p className="text-sm text-muted-foreground">Wonder watches the video, then SAM highlights each step's part. You can leave this page.</p>
        </Card>
      </Shell>
    )
  }

  if (job.status === 'failed' && !guide) {
    return (
      <Shell title={job.title || 'Guide'} back={{ name: 'home' }}>
        <ErrorNote message={job.error || 'Processing failed.'} />
      </Shell>
    )
  }

  if (!guide) return <Shell title="Guide" back={{ name: 'home' }}>{error ? <ErrorNote message={error} /> : <p className="text-muted-foreground">Loading…</p>}</Shell>

  const review = guide.steps.filter((s) => s.needs_review).length
  return (
    <Shell title={guide.title} back={{ name: 'home' }} actions={
      <>
        <Button variant="outline" size="sm" disabled={!dirty || saving} onClick={() => save(false)}>
          {saving ? <Loader2 className="animate-spin" /> : null}Save
        </Button>
        {guide.status === 'published' && !dirty
          ? <Button asChild size="sm"><a href={href({ name: 'coach', id: guide.id })}><Play />Coach</a></Button>
          : <Button size="sm" disabled={saving} onClick={() => save(true)}><Check />Publish</Button>}
      </>
    }>
      <div className="mb-6 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Badge variant={guide.status === 'published' ? 'ok' : 'outline'}>{guide.status === 'published' ? 'Published' : 'Draft'}</Badge>
        <span>{guide.steps.length} steps · {mmss(guide.duration_s)} video</span>
        {review > 0 && <Badge variant="warn"><AlertTriangle />{review} to review</Badge>}
        {dirty && <span>· unsaved changes</span>}
      </div>
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      <ol className="grid gap-4">
        {guide.steps.map((s) => <StepEditor key={s.step_no} guideId={guide.id} step={s} onChange={(p) => updateStep(s.step_no, p)} />)}
      </ol>
    </Shell>
  )
}

const lines = (xs: string[]) => xs.join('\n')
const fromLines = (t: string) => t.split('\n').map((x) => x.trim()).filter(Boolean)

function StepEditor({ guideId, step, onChange }: { guideId: string; step: Step; onChange: (p: Partial<Step>) => void }) {
  const f = (name: string) => `s${step.step_no}-${name}`
  return (
    <li>
      <Card className="gap-0 overflow-hidden py-0 md:flex-row">
        <div className="relative bg-muted md:w-80 md:shrink-0">
          {step.keyframe
            ? <img src={fileUrl(guideId, step.keyframe)} alt={`Step ${step.step_no} keyframe`} className="aspect-video w-full object-cover md:h-full" />
            : <div className="grid aspect-video place-items-center text-sm text-muted-foreground">No keyframe yet</div>}
          {step.needs_review && <Badge variant="warn" className="absolute top-2 left-2"><AlertTriangle />Part not found</Badge>}
        </div>
        <div className="grid flex-1 gap-4 p-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold">Step {step.step_no}</span>
            <span className="text-sm text-muted-foreground tabular-nums">{mmss(step.start_s)}–{mmss(step.end_s)}</span>
            <label className="ml-auto flex items-center gap-2 text-sm">
              Check this step <Switch checked={step.critical} onCheckedChange={(v) => onChange({ critical: v })} />
            </label>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={f('instr')}>Instruction (spoken to the junior)</Label>
            <Textarea id={f('instr')} value={step.instruction} onChange={(e) => onChange({ instruction: e.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor={f('parts')}>Parts, main one first</Label>
              <Input id={f('parts')} value={step.parts.join(', ')}
                onChange={(e) => onChange({ parts: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={f('tools')}>Tools</Label>
              <Input id={f('tools')} value={step.tools.join(', ')}
                onChange={(e) => onChange({ tools: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={f('hint')}>Done correctly looks like</Label>
            <Input id={f('hint')} value={step.check_hint} onChange={(e) => onChange({ check_hint: e.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor={f('tips')}>Expert's tips, one per line</Label>
              <Textarea id={f('tips')} value={lines(step.expert_tips)} onChange={(e) => onChange({ expert_tips: fromLines(e.target.value) })} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={f('warn')}>Warnings, one per line</Label>
              <Textarea id={f('warn')} value={lines(step.warnings)} onChange={(e) => onChange({ warnings: fromLines(e.target.value) })} />
            </div>
          </div>
        </div>
      </Card>
    </li>
  )
}
