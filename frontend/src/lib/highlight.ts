import type { Box } from './api'

/** A box as % of its picture, so the overlay lines up at any display size. */
export function highlightStyle(box: Box) {
  return {
    left: `${(box.x1 / box.w) * 100}%`,
    top: `${(box.y1 / box.h) * 100}%`,
    width: `${((box.x2 - box.x1) / box.w) * 100}%`,
    height: `${((box.y2 - box.y1) / box.h) * 100}%`,
  }
}
