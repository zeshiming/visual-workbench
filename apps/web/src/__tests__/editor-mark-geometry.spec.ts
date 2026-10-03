import { describe, expect, it } from 'vitest'

import {
  clampEditorMarkCenter,
  createEditorMarkFromDrag,
  findEditorMarkAtPoint,
  isPointInsideEditorMark,
  moveEditorMark,
} from '../lib/editor-mark-geometry'
import type { EditorMark } from '../types/editor-mark'

const sampleMark: EditorMark = {
  id: 'mark-1',
  centerX: 0.5,
  centerY: 0.5,
  radius: 0.1,
  description: '',
}

describe('createEditorMarkFromDrag', () => {
  it('creates a normalized mark from drag coordinates', () => {
    const mark = createEditorMarkFromDrag(
      { x: 600, y: 450 },
      { x: 800, y: 650 },
      1200,
      900,
    )

    expect(mark).toMatchObject({
      centerX: 0.5,
      centerY: 0.5,
      description: '',
    })
    expect(mark?.radius).toBeGreaterThan(0.1)
  })

  it('returns null when drag is too small', () => {
    const mark = createEditorMarkFromDrag(
      { x: 600, y: 450 },
      { x: 605, y: 452 },
      1200,
      900,
    )

    expect(mark).toBeNull()
  })
})

describe('findEditorMarkAtPoint', () => {
  it('finds the topmost mark at a point', () => {
    const marks: EditorMark[] = [
      { ...sampleMark, id: 'mark-1', centerX: 0.5, centerY: 0.5 },
      { ...sampleMark, id: 'mark-2', centerX: 0.52, centerY: 0.52 },
    ]

    expect(findEditorMarkAtPoint({ x: 610, y: 460 }, marks, 1200, 900)?.id).toBe('mark-2')
  })

  it('returns null when point is outside marks', () => {
    expect(findEditorMarkAtPoint({ x: 100, y: 100 }, [sampleMark], 1200, 900)).toBeNull()
  })
})

describe('moveEditorMark', () => {
  it('moves mark center in image coordinates', () => {
    const moved = moveEditorMark(sampleMark, { x: 720, y: 540 }, 1200, 900)

    expect(moved.centerX).toBeCloseTo(0.6, 5)
    expect(moved.centerY).toBeCloseTo(0.6, 5)
  })

  it('clamps mark center inside image bounds', () => {
    const moved = moveEditorMark(sampleMark, { x: 10, y: 10 }, 1200, 900)
    const clamped = clampEditorMarkCenter(sampleMark, moved.centerX, moved.centerY, 1200, 900)

    expect(moved.centerX).toBe(clamped.centerX)
    expect(moved.centerY).toBe(clamped.centerY)
    expect(isPointInsideEditorMark({ x: moved.centerX * 1200, y: moved.centerY * 900 }, moved, 1200, 900)).toBe(
      true,
    )
  })
})
