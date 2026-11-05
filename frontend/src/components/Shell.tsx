import type { ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { href, type Route } from '@/lib/router'
import { DemoBadge } from '@/components/DemoBadge'

/** Page frame for the desk screens: a plain top bar, a centred column. */
export function Shell({ title, back, actions, children }: {
  title: string; back?: Route; actions?: ReactNode; children: ReactNode
}) {
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
          {back && (
            <Button asChild variant="ghost" size="icon" aria-label="Back">
              <a href={href(back)}><ArrowLeft /></a>
            </Button>
          )}
          <h1 className="min-w-0 flex-1 truncate text-base font-semibold">{title}</h1>
          <DemoBadge />
          {actions}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">{message}</p>
}
