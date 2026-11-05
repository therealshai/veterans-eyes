// Types mirror backend/models.py. One function per API route (backend/app.py).

export type Box = { x1: number; y1: number; x2: number; y2: number; w: number; h: number; score?: number | null }

export type Step = {
  step_no: number
  start_s: number
  end_s: number
  instruction: string
  parts: string[]
  tools: string[]
  expert_tips: string[]
  warnings: string[]
  critical: boolean
  check_hint: string
  keyframe?: string | null
  keyframe_s?: number | null
  highlight?: Box | null
  highlight_part?: string | null
  needs_review?: boolean
}

export type Status = 'processing' | 'draft' | 'published' | 'failed'

export type Guide = {
  id: string
  title: string
  domain: string
  source_video: string
  duration_s: number
  status: Status
  steps: Step[]
}

export type GuideSummary = {
  id: string
  title: string
  domain: string
  status: Status
  progress: string
  steps: number
  critical_steps: number
  duration_s: number
  cover?: string | null
}

export type Job = { status?: Status; progress?: string; error?: string | null; title?: string }
export type AskResult = { answer: string; seconds: number }
export type CheckResult = { verdict: 'match' | 'fix' | 'unclear'; say: string; highlight: Box | null; seconds: number }

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const fileUrl = (guideId: string, name: string) =>
  `/api/guides/${encodeURIComponent(guideId)}/files/${encodeURIComponent(name)}`

export const api = {
  listGuides: () => fetch('/api/guides').then(json<GuideSummary[]>),

  getGuide: (id: string) =>
    fetch(`/api/guides/${encodeURIComponent(id)}`).then(json<{ job: Job; guide: Guide | null }>),

  saveGuide: (g: Guide) =>
    fetch(`/api/guides/${encodeURIComponent(g.id)}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(g),
    }).then(json<Guide>),

  publish: (id: string) =>
    fetch(`/api/guides/${encodeURIComponent(id)}/publish`, { method: 'POST' }).then(json<Guide>),

  /** XMLHttpRequest instead of fetch: it reports upload progress (videos are large). */
  createGuide(form: FormData, onProgress: (pct: number) => void): Promise<GuideSummary> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/guides')
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress((e.loaded / e.total) * 100)
      xhr.onload = () => (xhr.status < 300 ? resolve(JSON.parse(xhr.responseText)) : reject(new Error(xhr.responseText || xhr.statusText)))
      xhr.onerror = () => reject(new Error('Upload failed: check the connection'))
      xhr.send(form)
    })
  },

  ask(guideId: string, stepNo: number, question: string, frame: Blob | null) {
    const f = new FormData()
    f.append('guide_id', guideId); f.append('step_no', String(stepNo)); f.append('question', question)
    if (frame) f.append('frame', frame, 'frame.jpg')
    return fetch('/api/coach/ask', { method: 'POST', body: f }).then(json<AskResult>)
  },

  check(guideId: string, stepNo: number, frame: Blob) {
    const f = new FormData()
    f.append('guide_id', guideId); f.append('step_no', String(stepNo)); f.append('frame', frame, 'frame.jpg')
    return fetch('/api/coach/check', { method: 'POST', body: f }).then(json<CheckResult>)
  },
}
