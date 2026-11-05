import { useEffect, useState } from 'react'
import { AlertTriangle, CircleCheck, MessageCircle, ScanSearch } from 'lucide-react'
import { Shell } from '@/components/Shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { api, type Guide } from '@/lib/api'
import { mmss } from '@/lib/format'
import { href } from '@/lib/router'
import { loadSession, summarizeSession } from '@/lib/session'

/** End of a session: what was done, what the checks caught, how long it took. */
export default function Summary({ id }: { id: string }) {
  const [guide, setGuide] = useState<Guide | null>(null)
  const session = loadSession(id)
  useEffect(() => { api.getGuide(id).then(({ guide }) => setGuide(guide)).catch(() => {}) }, [id])

  if (!session) {
    return <Shell title="Summary" back={{ name: 'home' }}><p className="text-muted-foreground">No session recorded in this browser.</p></Shell>
  }
  const ev = session.events
  const counts = summarizeSession(session)
  const total = ((session.endedAt ?? Date.now()) - session.startedAt) / 1000

  const stats = [
    { label: 'Total time', value: mmss(total), icon: null },
    { label: 'Checks passed', value: `${counts.passes}`, icon: <ScanSearch className="size-4" /> },
    { label: 'Mistakes caught', value: `${counts.fixes}`, icon: <AlertTriangle className="size-4" /> },
    { label: 'Questions asked', value: `${counts.asks}`, icon: <MessageCircle className="size-4" /> },
  ]

  return (
    <Shell title="Summary" back={{ name: 'home' }}>
      <div className="mb-6 flex items-center gap-3">
        <CircleCheck className="size-8 text-ok" />
        <div>
          <p className="text-xl font-semibold">Job finished</p>
          {guide && <p className="text-sm">{guide.title}</p>}
          <p className="text-muted-foreground">{session.source === 'replay' ? 'Replay session' : 'Live session'}{counts.skipped ? ` · ${counts.skipped} check skipped` : ''}</p>
        </div>
      </div>
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label} className="gap-1 px-4 py-4">
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">{s.icon}{s.label}</p>
            <p className="text-2xl font-semibold tabular-nums">{s.value}</p>
          </Card>
        ))}
      </div>
      <h2 className="mb-3 font-semibold">What happened</h2>
      <ol className="grid gap-2">
        {ev.filter((e) => e.kind !== 'step').map((e, i) => (
          <li key={i} className="flex gap-3 rounded-lg border px-4 py-3">
            <span className="w-16 shrink-0 text-sm text-muted-foreground tabular-nums">{mmss((e.at - session.startedAt) / 1000)}</span>
            <span className="w-14 shrink-0 text-sm font-medium">Step {e.step}</span>
            <span className="text-sm">
              {e.kind === 'check' && <>{e.verdict === 'match' ? 'Check passed' : e.verdict === 'fix' ? 'Caught: ' : 'Unclear: '}{e.verdict !== 'match' && e.say}</>}
              {e.kind === 'ask' && <>“{e.question}” → {e.answer}</>}
              {e.kind === 'skip-check' && 'Check skipped'}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-8 flex gap-2">
        <Button asChild variant="outline"><a href={href({ name: 'home' })}>All guides</a></Button>
        <Button asChild><a href={href({ name: 'coach', id })}>Coach again</a></Button>
      </div>
    </Shell>
  )
}
