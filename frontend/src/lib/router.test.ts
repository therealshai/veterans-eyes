import { describe, expect, it } from 'vitest'
import { href, parse, type Route } from './router'

describe('parse', () => {
  it('matches every route', () => {
    expect(parse('')).toEqual({ name: 'home' })
    expect(parse('#/')).toEqual({ name: 'home' })
    expect(parse('#/new')).toEqual({ name: 'new' })
    expect(parse('#/guides/abc/review')).toEqual({ name: 'review', id: 'abc' })
    expect(parse('#/guides/abc/coach')).toEqual({ name: 'coach', id: 'abc' })
    expect(parse('#/guides/abc/summary')).toEqual({ name: 'summary', id: 'abc' })
  })

  it('falls back to home', () => {
    expect(parse('#/nope')).toEqual({ name: 'home' })
    expect(parse('#/guides/abc')).toEqual({ name: 'home' })
    expect(parse('#/guides/abc/edit')).toEqual({ name: 'home' })
    expect(parse('#/guides')).toEqual({ name: 'home' })
  })

  it('decodes odd ids', () => {
    expect(parse('#/guides/a%20b/coach')).toEqual({ name: 'coach', id: 'a b' })
    expect(parse('#/guides/x%2Fy/review')).toEqual({ name: 'review', id: 'x/y' })
    expect(parse('#/guides/caf%C3%A9/summary')).toEqual({ name: 'summary', id: 'café' })
  })
})

describe('href round trips', () => {
  const routes: Route[] = [
    { name: 'home' },
    { name: 'new' },
    { name: 'review', id: 'abc' },
    { name: 'coach', id: 'a b' },
    { name: 'coach', id: 'x/y' },
    { name: 'summary', id: 'café' },
    { name: 'review', id: 'a%20b' },
  ]
  for (const r of routes) {
    it(JSON.stringify(r), () => expect(parse(href(r))).toEqual(r))
  }
})
