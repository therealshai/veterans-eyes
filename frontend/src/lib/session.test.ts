import { describe, expect, it } from 'vitest'
import { summarizeSession, type Session } from './session'

const session = (kinds: Array<'step' | 'match' | 'fix' | 'unclear' | 'ask' | 'skip'>): Session => ({
  guideId: 'g',
  startedAt: 1000,
  endedAt: 2000,
  source: 'camera',
  events: kinds.map((k, i) => {
    const base = { step: 1, at: 1000 + i }
    if (k === 'step') return { kind: 'step' as const, ...base }
    if (k === 'ask') return { kind: 'ask' as const, ...base, question: 'q', answer: 'a', seconds: 1 }
    if (k === 'skip') return { kind: 'skip-check' as const, ...base }
    return { kind: 'check' as const, ...base, verdict: k, say: 's', seconds: 1 }
  }),
})

describe('summarizeSession', () => {
  it('counts fixes, passes, asks and skips', () => {
    expect(summarizeSession(session(['step', 'match', 'fix', 'fix', 'unclear', 'ask', 'ask', 'skip'])))
      .toEqual({ checks: 4, fixes: 2, passes: 1, unclear: 1, asks: 2, skipped: 1 })
  })

  it('ignores step events and starts at zero', () => {
    expect(summarizeSession(session([])))
      .toEqual({ checks: 0, fixes: 0, passes: 0, unclear: 0, asks: 0, skipped: 0 })
    expect(summarizeSession(session(['step', 'step']))?.checks).toBe(0)
  })
})
