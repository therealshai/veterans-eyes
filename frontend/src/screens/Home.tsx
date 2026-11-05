import { useEffect, useState } from 'react'
import { AlertTriangle, Loader2, Plus } from 'lucide-react'
import { Shell, ErrorNote } from '@/components/Shell'
import { DemoNote } from '@/components/DemoBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { api, fileUrl, type GuideSummary } from '@/lib/api'
import { mmss, plural } from '@/lib/format'
import { href } from '@/lib/router'

const STATUS: Record<GuideSummary['status'], { label: string; variant: 'secondary' | 'outline' | 'ok' | 'destructive' }> = {
  processing: { label: 'Processing', variant: 'secondary' },
  draft: { label: 'Draft', variant: 'secondary' },
  published: { label: 'Published', variant: 'ok' },
  failed: { label: 'Failed', variant: 'destructive' },
}

export default function Home() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    const load = () =>
      api.listGuides()
        .then((g) => {
          if (!alive) return
          setGuides(g); setError('')
          // Poll only while something is processing.
          if (g.some((x) => x.status === 'processing')) timer = window.setTimeout(load, 3000)
        })
        .catch((e) => alive && setError(e.message))
    load()
    return () => { alive = false; window.clearTimeout(timer) }
  }, [])

  return (
    <Shell title="Veteran's Eyes" actions={
      <Button asChild size="sm"><a href={href({ name: 'new' })}><Plus />New guide</a></Button>
    }>
      <p className="mb-6 max-w-prose text-muted-foreground">
        A senior records one narrated repair. Juniors follow it step by step, with spoken steps, answers and checks.
      </p>
      <DemoNote />
      {error && <ErrorNote message={`Can't reach the server: ${error}`} />}
      {guides === null && !error && <p className="text-muted-foreground">Loading guides…</p>}
      {guides?.length === 0 && (
        <Card className="items-center px-6 py-12 text-center">
          <p className="font-medium">No guides yet</p>
          <p className="text-sm text-muted-foreground">Upload a narrated repair video to create the first one.</p>
          <Button asChild><a href={href({ name: 'new' })}><Plus />New guide</a></Button>
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {guides?.map((g) => <GuideCard key={g.id} g={g} />)}
      </div>
    </Shell>
  )
}

function GuideCard({ g }: { g: GuideSummary }) {
  const status = STATUS[g.status]
  const ready = g.status === 'draft' || g.status === 'published'
  return (
    <Card className="gap-0 overflow-hidden py-0">
      <div className="relative aspect-video bg-muted">
        {g.cover
          ? <img src={fileUrl(g.id, g.cover)} alt="" className="size-full object-cover" loading="lazy" />
          : <div className="grid size-full place-items-center text-muted-foreground">
              {g.status === 'processing' ? <Loader2 className="size-6 animate-spin" /> : g.status === 'failed' ? <AlertTriangle className="size-6" /> : null}
            </div>}
        <Badge variant={status.variant} className="absolute top-2 left-2">{status.label}</Badge>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h2 className="font-semibold leading-snug">{g.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {g.status === 'processing'
              ? g.progress || 'Processing…'
              : `${plural(g.steps, 'step')} · ${plural(g.critical_steps, 'check')} · ${mmss(g.duration_s)}`}
          </p>
        </div>
        {ready && (
          <div className="mt-auto flex gap-2">
            <Button asChild variant="outline" className="flex-1"><a href={href({ name: 'review', id: g.id })}>Review</a></Button>
            <Button asChild className="flex-1"><a href={href({ name: 'coach', id: g.id })}>Start coaching</a></Button>
          </div>
        )}
        {g.status === 'failed' && (
          <Button asChild variant="outline"><a href={href({ name: 'review', id: g.id })}>See error</a></Button>
        )}
      </div>
    </Card>
  )
}
