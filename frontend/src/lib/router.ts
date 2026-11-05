import { useSyncExternalStore } from 'react'

// Hash routing (#/guides/x/coach): works when FastAPI serves the built files,
// with no server-side route config. Five routes, so no router library.

export type Route =
  | { name: 'home' }
  | { name: 'new' }
  | { name: 'review'; id: string }
  | { name: 'coach'; id: string }
  | { name: 'summary'; id: string }

export function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  if (parts[0] === 'new') return { name: 'new' }
  if (parts[0] === 'guides' && parts[1]) {
    if (parts[2] === 'review') return { name: 'review', id: parts[1] }
    if (parts[2] === 'coach') return { name: 'coach', id: parts[1] }
    if (parts[2] === 'summary') return { name: 'summary', id: parts[1] }
  }
  return { name: 'home' }
}

export function href(r: Route): string {
  if (r.name === 'home') return '#/'
  if (r.name === 'new') return '#/new'
  return `#/guides/${encodeURIComponent(r.id)}/${r.name}`
}

export const go = (r: Route) => { window.location.hash = href(r) }

const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash)
  return parse(hash)
}
