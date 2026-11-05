// @vitest-environment jsdom
// iOS Safari speaks only if speech first starts inside a tap: every SourcePicker
// entry must call speechSynthesis.speak synchronously within the click/change.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { SourcePicker } from './Coach'
import type { Guide } from '@/lib/api'

const speak = vi.fn()
class FakeUtterance {
  text: string
  constructor(text: string) { this.text = text }
}

afterEach(() => cleanup())
beforeEach(() => {
  speak.mockClear()
  vi.stubGlobal('speechSynthesis', { speak, cancel: vi.fn(), getVoices: () => [] })
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:fake' })
})

const guide = { id: 'g', title: 'Chain', steps: [{ step_no: 1, critical: true }] } as unknown as Guide

describe('SourcePicker speech unlock', () => {
  it('camera start speaks synchronously in the click', () => {
    const onPick = vi.fn()
    render(<SourcePicker guide={guide} onPick={onPick} />)
    fireEvent.click(screen.getByRole('button', { name: /Start with camera/ }))
    // No await between click and assert: speak ran inside the tap, before anything async.
    expect(speak).toHaveBeenCalledTimes(1)
    expect((speak.mock.calls[0][0] as FakeUtterance).text).toBe(' ')
    expect(onPick).toHaveBeenCalledWith({ kind: 'camera' })
  })

  it('expert replay speaks synchronously in the click', () => {
    const onPick = vi.fn()
    render(<SourcePicker guide={guide} onPick={onPick} />)
    fireEvent.click(screen.getByRole('button', { name: /Replay the expert's video/ }))
    expect(speak).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith({ kind: 'replay', url: '/api/guides/g/files/video.mp4', followSteps: true })
  })

  it('file replay speaks synchronously in the change event', () => {
    const onPick = vi.fn()
    const { container } = render(<SourcePicker guide={guide} onPick={onPick} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'v.mp4', { type: 'video/mp4' })] } })
    expect(speak).toHaveBeenCalledTimes(1)
    expect(onPick).toHaveBeenCalledWith({ kind: 'replay', url: 'blob:fake' })
  })
})
