import type { EditorMark } from '@/types/editor-mark'

const MIN_RADIUS_NORM = 0.015

export function createEditorMarkId(): string {
  return `mark-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function getEditorMarkRadiusPx(
  mark: EditorMark,
  imageWidth: number,
  imageHeight: number,
): number {
  return mark.radius * Math.min(imageWidth, imageHeight)
}

export function getEditorMarkCenterPx(
  mark: EditorMark,
  imageWidth: number,
  imageHeight: number,
): { x: number; y: number } {
  return {
    x: mark.centerX * imageWidth,
    y: mark.centerY * imageHeight,
  }
}

export function findEditorMarkAtPoint(
  point: { x: number; y: number },
  marks: EditorMark[],
  imageWidth: number,
  imageHeight: number,
): EditorMark | null {
  if (!imageWidth || !imageHeight) {
    return null
  }

  for (let index = marks.length - 1; index >= 0; index -= 1) {
    const mark = marks[index]!

    if (!isPointInsideEditorMark(point, mark, imageWidth, imageHeight)) {
      continue
    }

    return mark
  }

  return null
}

export function isPointInsideEditorMark(
  point: { x: number; y: number },
  mark: EditorMark,
  imageWidth: number,
  imageHeight: number,
): boolean {
  const center = getEditorMarkCenterPx(mark, imageWidth, imageHeight)
  const radius = getEditorMarkRadiusPx(mark, imageWidth, imageHeight)

  return Math.hypot(point.x - center.x, point.y - center.y) <= radius
}

export function clampEditorMarkCenter(
  mark: EditorMark,
  centerX: number,
  centerY: number,
  imageWidth: number,
  imageHeight: number,
): { centerX: number; centerY: number } {
  const base = Math.min(imageWidth, imageHeight)
  const radiusX = (mark.radius * base) / imageWidth
  const radiusY = (mark.radius * base) / imageHeight

  return {
    centerX: Math.min(1 - radiusX, Math.max(radiusX, centerX)),
    centerY: Math.min(1 - radiusY, Math.max(radiusY, centerY)),
  }
}

export function moveEditorMark(
  mark: EditorMark,
  centerPx: { x: number; y: number },
  imageWidth: number,
  imageHeight: number,
): EditorMark {
  const nextCenter = clampEditorMarkCenter(
    mark,
    centerPx.x / imageWidth,
    centerPx.y / imageHeight,
    imageWidth,
    imageHeight,
  )

  return {
    ...mark,
    centerX: nextCenter.centerX,
    centerY: nextCenter.centerY,
  }
}

export function createEditorMarkFromDrag(
  start: { x: number; y: number },
  end: { x: number; y: number },
  imageWidth: number,
  imageHeight: number,
): EditorMark | null {
  if (!imageWidth || !imageHeight) {
    return null
  }

  const imageBase = Math.min(imageWidth, imageHeight)
  const radiusPx = Math.hypot(end.x - start.x, end.y - start.y)
  const radiusNorm = radiusPx / imageBase

  if (radiusNorm < MIN_RADIUS_NORM) {
    return null
  }

  return {
    id: createEditorMarkId(),
    centerX: start.x / imageWidth,
    centerY: start.y / imageHeight,
    radius: radiusNorm,
    description: '',
  }
}
