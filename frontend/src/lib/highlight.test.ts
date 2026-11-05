import { describe, expect, it } from 'vitest'
import { highlightStyle } from './highlight'

describe('highlightStyle', () => {
  it('converts pixels to % of the picture', () => {
    expect(highlightStyle({ x1: 10, y1: 20, x2: 30, y2: 60, w: 100, h: 200 }))
      .toEqual({ left: '10%', top: '10%', width: '20%', height: '20%' })
  })

  it('covers the full picture when the box is at the edges', () => {
    expect(highlightStyle({ x1: 0, y1: 0, x2: 640, y2: 480, w: 640, h: 480 }))
      .toEqual({ left: '0%', top: '0%', width: '100%', height: '100%' })
  })

  it('handles a 1 px box in the bottom-right corner', () => {
    expect(highlightStyle({ x1: 639, y1: 479, x2: 640, y2: 480, w: 640, h: 480 }))
      .toEqual({ left: '99.84375%', top: '99.79166666666667%', width: '0.15625%', height: '0.20833333333333334%' })
  })

  it('uses the frame size, not the displayed video size', () => {
    // SAM saw a 960x540 frame; the phone shows it smaller. % keeps the overlay lined up.
    expect(highlightStyle({ x1: 256, y1: 168, x2: 371, y2: 288, w: 960, h: 540 }))
      .toEqual({
        left: '26.666666666666668%', top: '31.11111111111111%',
        width: '11.979166666666668%', height: '22.22222222222222%',
      })
  })
})
