import { cn } from '@/lib/utils'

/** A thin bar, value 0..100. */
function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)}
      className={cn('relative h-1.5 w-full overflow-hidden rounded-full bg-secondary', className)}>
      <div className="h-full bg-primary transition-[width] duration-300" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}
export { Progress }
