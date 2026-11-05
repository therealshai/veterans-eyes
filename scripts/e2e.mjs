// End to end: the real app in a phone viewport against a fake-mode backend (no credits).
//
//   npm run e2e            (first time only: npx playwright install chromium)
//   PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers npm run e2e     (custom browser location)
//
// Flow: home -> upload a test video -> wait for draft -> edit a step -> publish ->
// Coach in replay mode -> hold-to-ask -> check a critical step -> finish -> Summary.
// A screenshot per screen goes to docs/screenshots/. Any console error fails the run.
import { spawn, spawnSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const BASE = 'http://127.0.0.1:8000'
const SHOTS = join(ROOT, 'docs', 'screenshots')
const VIDEO = '/tmp/ve_e2e.mp4'

const step = (n, ...msg) => console.log(`[e2e ${n}]`, ...msg)
const fail = (msg) => { throw new Error(msg) }

function makeVideo() {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=10',
    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5', '-t', '5', '-pix_fmt', 'yuv420p',
    '-shortest', VIDEO])
  if (r.status !== 0) fail('ffmpeg could not make the test video')
}

async function startBackend() {
  const proc = spawn('python', ['-m', 'uvicorn', 'backend.app:app', '--port', '8000'],
    { cwd: ROOT, env: { ...process.env, VE_FAKE: '1' }, stdio: ['ignore', 'pipe', 'pipe'] })
  let log = ''
  proc.stderr.on('data', (d) => { log += d })
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`${BASE}/api/health`)
      if (r.ok) return { proc, log: () => log }
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 1000))
  }
  proc.kill()
  fail(`backend never came up:\n${log.slice(-2000)}`)
}

async function main() {
  mkdirSync(SHOTS, { recursive: true })
  makeVideo()
  const { proc, log } = await startBackend()
  step(0, 'fake-mode backend up')
  const errors = []
  const browser = await chromium.launch({
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  })
  let guideId = ''
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true })
    page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })
    page.on('pageerror', (e) => errors.push(`page: ${e.message}`))

    // 1. Home -> New guide
    await page.goto(BASE, { waitUntil: 'networkidle' })
    await page.getByRole('link', { name: 'New guide' }).first().click()
    await page.getByLabel('Job name').fill('E2E test guide')
    await page.locator('#video').setInputFiles(VIDEO)
    await page.screenshot({ path: join(SHOTS, 'new.png') })
    await page.getByRole('button', { name: 'Create guide' }).click()

    // 2. Review: wait for draft, edit a step, publish
    await page.getByRole('button', { name: 'Publish' }).waitFor({ timeout: 120000 })
    step(2, 'draft ready')
    await page.screenshot({ path: join(SHOTS, 'review.png') })
    await page.locator('#s1-instr').fill('E2E edited: loosen the cover screws')
    const save = page.getByRole('button', { name: 'Save' })
    await save.click()
    await page.getByText('unsaved changes').waitFor({ state: 'detached', timeout: 10000 })
    step(2, 'edit saved')
    await page.getByRole('button', { name: 'Publish' }).click()
    await page.getByText('Published').first().waitFor({ timeout: 15000 })
    step(2, 'published')
    guideId = new URL(page.url()).hash.split('/')[2]

    // 3. Coach in replay mode
    await page.getByRole('link', { name: 'Coach' }).click()
    await page.getByRole('button', { name: "Replay the expert's video" }).click()
    const talk = page.getByRole('button', { name: /Hold to ask|Listening/ })
    await page.waitForFunction(
      () => [...document.querySelectorAll('button')].some((b) => /Hold to ask/.test(b.textContent) && !b.disabled),
      null, { timeout: 30000 })
    step(3, 'coach ready')
    await page.screenshot({ path: join(SHOTS, 'coach.png') })

    // 4. Hold to ask (fake mic + fake ASR answer the canned question)
    await talk.hover()
    await page.mouse.down()
    await page.waitForTimeout(1500)
    await page.mouse.up()
    await page.getByText('Turn it anticlockwise').waitFor({ timeout: 20000 })
    step(4, 'spoken answer shown')
    await page.screenshot({ path: join(SHOTS, 'coach-ask.png') })

    // 5. Walk every step: check critical ones, skip a failed check, finish
    for (let i = 0; i < 8; i++) {
      const finish = page.getByRole('button', { name: 'Finish' })
      if (await finish.isVisible()) {
        await finish.click()
        break
      }
      const checkBtn = page.getByRole('button', { name: 'Check my work' })
      if (await checkBtn.isVisible()) {
        await checkBtn.click()
        await page.getByRole('status').first().waitFor({ timeout: 20000 })
        await page.screenshot({ path: join(SHOTS, 'coach-check.png') })
        const skip = page.getByRole('button', { name: 'Skip check and continue' })
        if (await skip.isVisible()) await skip.click() // verdict was fix/unclear: skip on purpose
        step(5, 'check done')
      }
      const next = page.getByRole('button', { name: 'Done, next step' })
      if (await next.isVisible()) await next.click()
    }

    // 6. Summary
    await page.getByText('Job finished').waitFor({ timeout: 15000 })
    await page.screenshot({ path: join(SHOTS, 'summary.png') })
    for (const label of ['Checks passed', 'Mistakes caught', 'Questions asked']) {
      if (!(await page.getByText(label).isVisible())) fail(`summary misses "${label}"`)
    }
    step(6, 'summary shown')
    await page.goto(`${BASE}#/`, { waitUntil: 'networkidle' })
    await page.screenshot({ path: join(SHOTS, 'home.png') })

    if (errors.length) fail(`${errors.length} console error(s):\n- ${errors.join('\n- ')}`)
    console.log('[e2e] PASS: no console errors, screenshots in docs/screenshots/')
  } finally {
    await browser.close()
    proc.kill()
    if (guideId) rmSync(join(ROOT, 'data', 'guides', guideId), { recursive: true, force: true })
    const tail = log().slice(-2000)
    if (tail.match(/Traceback|ERROR/i)) console.log('[e2e] backend log tail:\n' + tail)
  }
}

main().catch((e) => { console.error('[e2e] FAIL:', e.message); process.exit(1) })
