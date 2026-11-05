import { FlaskConical } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useDemoMode } from '@/lib/config'

/** Shown whenever answers are canned, so nobody mistakes demo replies for real ones. */
export function DemoBadge() {
  const demo = useDemoMode()
  if (!demo) return null
  return (
    <Badge variant="warn" title="No API key: model answers are canned. Add META_API_KEY to .env for real answers.">
      <FlaskConical />Demo mode
    </Badge>
  )
}

export function DemoNote() {
  const demo = useDemoMode()
  if (!demo) return null
  return (
    <p className="mb-6 rounded-md border border-warn bg-warn/10 px-3 py-2 text-sm">
      <span className="font-medium">Demo mode:</span> no API key is set, so steps, answers and checks are canned examples.
      Add <code className="font-mono">META_API_KEY</code> to <code className="font-mono">.env</code> (see <code className="font-mono">.env.example</code>) for real ones.
    </p>
  )
}
