import { useState } from 'react'
import { Upload } from 'lucide-react'
import { Shell, ErrorNote } from '@/components/Shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { go } from '@/lib/router'

const DOMAINS = [
  { value: 'two-wheeler', label: 'Two-wheeler repair' },
  { value: 'bicycle', label: 'Bicycle repair' },
  { value: 'industrial-assembly', label: 'Industrial assembly' },
]

export default function NewGuide() {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [domain, setDomain] = useState('two-wheeler')
  const [dryRun, setDryRun] = useState(false)
  const [pct, setPct] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('video', file)
    form.append('title', title.trim() || file.name.replace(/\.[^.]+$/, ''))
    form.append('domain', domain)
    form.append('model', dryRun ? 'spark' : 'wonder')
    setError(''); setPct(0)
    try {
      const g = await api.createGuide(form, setPct)
      go({ name: 'review', id: g.id })       // the review screen shows progress until it's ready
    } catch (err) {
      setPct(null); setError((err as Error).message)
    }
  }

  return (
    <Shell title="New guide" back={{ name: 'home' }}>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Upload the senior's recording</CardTitle>
          <CardDescription>
            One narrated repair, start to finish. Film from the chest, keep the hands and parts in view, and say why as well as what.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-5">
            <div className="grid gap-2">
              <Label htmlFor="video">Video (MP4 or MOV)</Label>
              <Input id="video" type="file" accept="video/mp4,video/quicktime,video/*" required
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="title">Job name</Label>
              <Input id="title" placeholder="Air filter cover: remove and refit" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <fieldset className="grid gap-2">
              <legend className="mb-2 text-sm font-medium">Domain</legend>
              <div className="flex flex-wrap gap-2">
                {DOMAINS.map((d) => (
                  <Button key={d.value} type="button" variant={domain === d.value ? 'default' : 'outline'}
                    aria-pressed={domain === d.value} onClick={() => setDomain(d.value)}>{d.label}</Button>
                ))}
              </div>
            </fieldset>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              <span><span className="font-medium">Dry run with Spark</span><br />
                <span className="text-muted-foreground">Cheaper for testing; it hears narration less well than Wonder.</span></span>
            </label>
            {error && <ErrorNote message={error} />}
            {pct !== null && (
              <div className="grid gap-2">
                <Progress value={pct} />
                <p className="text-sm text-muted-foreground">Uploading… {Math.round(pct)}%</p>
              </div>
            )}
            <Button type="submit" size="touch" disabled={!file || pct !== null}><Upload />Create guide</Button>
            <p className="text-sm text-muted-foreground">Processing takes about a minute per minute of video.</p>
          </form>
        </CardContent>
      </Card>
    </Shell>
  )
}
