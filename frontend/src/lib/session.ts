// What happened in one coaching session, for the summary screen.
// Kept in sessionStorage so a page refresh doesn't lose it.

export type SessionEvent =
  | { kind: 'step'; step: number; at: number }
  | { kind: 'check'; step: number; at: number; verdict: 'match' | 'fix' | 'unclear'; say: string; seconds: number }
  | { kind: 'ask'; step: number; at: number; question: string; answer: string; seconds: number }
  | { kind: 'skip-check'; step: number; at: number }

export type Session = { guideId: string; startedAt: number; endedAt?: number; source: 'camera' | 'replay'; events: SessionEvent[] }

/** The Summary screen's counts: what the checks caught, asked and skipped. */
export function summarizeSession(s: Session) {
  const checks = s.events.filter((e) => e.kind === 'check')
  return {
    checks: checks.length,
    fixes: checks.filter((e) => e.verdict === 'fix').length,
    passes: checks.filter((e) => e.verdict === 'match').length,
    unclear: checks.filter((e) => e.verdict === 'unclear').length,
    asks: s.events.filter((e) => e.kind === 'ask').length,
    skipped: s.events.filter((e) => e.kind === 'skip-check').length,
  }
}

const KEY = (id: string) => `ve-session-${id}`

export function saveSession(s: Session) {
  try { sessionStorage.setItem(KEY(s.guideId), JSON.stringify(s)) } catch { /* private mode */ }
}

export function loadSession(guideId: string): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY(guideId))
    return raw ? (JSON.parse(raw) as Session) : null
  } catch { return null }
}
