import { useEffect, useState } from 'react'

// Asked once per page load: is the server in demo mode (canned model answers)?
let cached: Promise<{ demo: boolean }> | null = null
const load = () => (cached ??= fetch('/api/config').then((r) => r.json()).catch(() => ({ demo: false })))

export function useDemoMode(): boolean {
  const [demo, setDemo] = useState(false)
  useEffect(() => { load().then((c) => setDemo(!!c.demo)) }, [])
  return demo
}
