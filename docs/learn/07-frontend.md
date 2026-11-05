# 07 · The app (`frontend/`)

**One idea:** a small React app, plain shadcn components, five screens that each own their data.

## Stack, and why
| Piece | Job |
|---|---|
| Vite | dev server with instant reload; `npm run build` → static files in `dist/` |
| React + TypeScript | screens as components; types catch "wrong field name" before you run it |
| Tailwind v4 | styling with classes (`text-xl font-semibold`), configured in `src/index.css` |
| shadcn/ui | copy-in components in `src/components/ui/` (Button, Card, Badge, Input, Switch...): you own the code |
| lucide-react | icons |
| vitest | `npm test`: unit tests for the router, highlight %, session counts, worklet resampling |

## How it fits together
```
src/main.tsx          mounts <App/>, follows the system light/dark setting
src/App.tsx           picks the screen from the URL hash (#/guides/x/coach)
src/lib/router.ts     5 routes, no router library (useSyncExternalStore on hashchange)
src/lib/api.ts        one function per backend route; types copied from backend/models.py
src/screens/*.tsx     Home, NewGuide, Review, Coach, Summary
```
Hash routes (`#/...`) mean FastAPI serves one `index.html` and never needs to know the app's pages.

## Dev vs demo
- **Dev:** `uvicorn backend.app:app --reload` + `cd frontend && npm run dev` → http://localhost:5173.
  `vite.config.ts` forwards `/api` and `/ws` to :8000 (`server.proxy`, `ws: true`).
- **Demo:** `npm run build`, then only uvicorn: it serves `frontend/dist` at `/`. One server, one tunnel.

## Design rules in code
- Colors are tokens in `index.css`: zinc neutrals, `--warn` (amber, "look here"), `--ok` (green, passed).
- Button sizes `touch` (48 px) and `xl` (64 px, the talk button): see `components/ui/button.tsx`.
- Every AI moment shows its state in words: "Listening…", "Thinking…", "Comparing with the expert…".

## The Coach screen in one paragraph
On start a picker offers the live camera or a replay video standing in for it; then it opens
the camera + mic once, connects the voice socket, and takes a wake lock.
Each step change speaks the step. "Check my work" sends a frame to `/api/coach/check`, shows the
verdict and draws SAM's box over the video in percentages (so it lines up at any size). Critical
steps require a passed check (or an explicit skip, logged). Every event goes to `lib/session.ts`
for the Summary screen.

## Fake mode
`VE_FAKE=1 uvicorn backend.app:app` answers every model call with canned replies: click through,
restyle and rehearse with zero credits (`backend/fake.py`).
