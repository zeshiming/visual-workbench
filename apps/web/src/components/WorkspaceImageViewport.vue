<script setup lang="ts">
import { Maximize2 } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { EditorMark } from '@/types/editor-mark'

import {
  createEditorMarkFromDrag,
  findEditorMarkAtPoint,
  moveEditorMark,
} from '@/lib/editor-mark-geometry'

const props = withDefaults(
  defineProps<{
    src: string
    alt?: string
    annotationMode?: boolean
    marks?: EditorMark[]
  }>(),
  {
    alt: '工作区图片',
    annotationMode: false,
    marks: () => [],
  },
)

const emit = defineEmits<{
  'update:marks': [marks: EditorMark[]]
}>()

const { t } = useI18n()

const viewportRef = ref<HTMLDivElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)

const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isPanning = ref(false)
const isDrawing = ref(false)
const isMovingMark = ref(false)
const hoveredMarkId = ref<string | null>(null)

const drawPointerId = ref<number | null>(null)
const drawStartX = ref(0)
const drawStartY = ref(0)
const drawCurrentX = ref(0)
const drawCurrentY = ref(0)

const movingMarkId = ref<string | null>(null)
const movePointerId = ref<number | null>(null)
const movingMarkCenterPx = ref<{ x: number; y: number } | null>(null)
const moveStartCenterX = ref(0)
const moveStartCenterY = ref(0)
const moveStartPointerX = ref(0)
const moveStartPointerY = ref(0)

let panPointerId: number | null = null
let panStartX = 0
let panStartY = 0
let panStartTranslateX = 0
let panStartTranslateY = 0

const MIN_SCALE = 0.05
const MAX_SCALE = 20

const imageWidth = computed(() => loadedImageWidth.value)
const imageHeight = computed(() => loadedImageHeight.value)
const loadedImageWidth = ref(0)
const loadedImageHeight = ref(0)
const imageBase = computed(() => Math.min(imageWidth.value, imageHeight.value) || 1)
const strokeWidth = computed(() => Math.max(2, imageBase.value * 0.004))

const contentStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  transformOrigin: '0 0',
}))

const viewportCursor = computed(() => {
  if (isMovingMark.value) {
    return 'cursor-grabbing'
  }

  if (isDrawing.value) {
    return 'cursor-crosshair'
  }

  if (props.annotationMode && hoveredMarkId.value) {
    return 'cursor-grab'
  }

  if (props.annotationMode) {
    return 'cursor-crosshair'
  }

  return isPanning.value ? 'cursor-grabbing' : 'cursor-grab'
})

const drawingPreview = computed(() => {
  if (!isDrawing.value || !imageWidth.value || !imageHeight.value) {
    return null
  }

  const radius = Math.hypot(drawCurrentX.value - drawStartX.value, drawCurrentY.value - drawStartY.value)

  return {
    startX: drawStartX.value,
    startY: drawStartY.value,
    currentX: drawCurrentX.value,
    currentY: drawCurrentY.value,
    radius,
  }
})

const showAnnotationOverlay = computed(
  () =>
    Boolean(imageWidth.value && imageHeight.value) &&
    (displayMarks.value.length > 0 || drawingPreview.value !== null),
)

const displayMarks = computed(() => {
  if (!movingMarkId.value || !movingMarkCenterPx.value || !imageWidth.value || !imageHeight.value) {
    return props.marks
  }

  const mark = props.marks.find((item) => item.id === movingMarkId.value)

  if (!mark) {
    return props.marks
  }

  const movedMark = moveEditorMark(
    mark,
    movingMarkCenterPx.value,
    imageWidth.value,
    imageHeight.value,
  )

  return props.marks.map((item) => (item.id === movingMarkId.value ? movedMark : item))
})

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
}

function fitImageToViewport(): void {
  const viewport = viewportRef.value
  const imageWidthPx = imageRef.value?.naturalWidth || loadedImageWidth.value
  const imageHeightPx = imageRef.value?.naturalHeight || loadedImageHeight.value

  if (!viewport || !imageWidthPx || !imageHeightPx) {
    return
  }

  const { width: viewportWidth, height: viewportHeight } = viewport.getBoundingClientRect()
  const padding = 48
  const availableWidth = Math.max(viewportWidth - padding * 2, 1)
  const availableHeight = Math.max(viewportHeight - padding * 2, 1)

  const fitScale = Math.min(
    availableWidth / imageWidthPx,
    availableHeight / imageHeightPx,
    1,
  )

  scale.value = fitScale
  translateX.value = (viewportWidth - imageWidthPx * fitScale) / 2
  translateY.value = (viewportHeight - imageHeightPx * fitScale) / 2
}

function clientToImagePoint(clientX: number, clientY: number): { x: number; y: number } | null {
  const viewport = viewportRef.value

  if (!viewport) {
    return null
  }

  const rect = viewport.getBoundingClientRect()

  return {
    x: (clientX - rect.left - translateX.value) / scale.value,
    y: (clientY - rect.top - translateY.value) / scale.value,
  }
}

function updateHoveredMark(point: { x: number; y: number } | null): void {
  if (!props.annotationMode || isDrawing.value || isMovingMark.value || !point) {
    hoveredMarkId.value = null
    return
  }

  hoveredMarkId.value =
    findEditorMarkAtPoint(point, props.marks, imageWidth.value, imageHeight.value)?.id ?? null
}

function emitMovedMark(markId: string, centerPx: { x: number; y: number }): void {
  const mark = props.marks.find((item) => item.id === markId)

  if (!mark) {
    return
  }

  const nextMark = moveEditorMark(mark, centerPx, imageWidth.value, imageHeight.value)
  emit(
    'update:marks',
    props.marks.map((item) => (item.id === markId ? nextMark : item)),
  )
}

function finishDrawing(): void {
  if (!isDrawing.value) {
    drawPointerId.value = null
    return
  }

  const nextMark = createEditorMarkFromDrag(
    { x: drawStartX.value, y: drawStartY.value },
    { x: drawCurrentX.value, y: drawCurrentY.value },
    imageWidth.value,
    imageHeight.value,
  )

  if (nextMark) {
    emit('update:marks', [...props.marks, nextMark])
  }

  isDrawing.value = false
  drawPointerId.value = null
}

function finishMovingMark(event?: PointerEvent): void {
  if (isMovingMark.value && movingMarkId.value && movingMarkCenterPx.value) {
    emitMovedMark(movingMarkId.value, movingMarkCenterPx.value)
  }

  isMovingMark.value = false
  movingMarkId.value = null
  movePointerId.value = null
  movingMarkCenterPx.value = null

  if (event) {
    updateHoveredMark(clientToImagePoint(event.clientX, event.clientY))
  }
}

function zoomAt(clientX: number, clientY: number, delta: number): void {
  const viewport = viewportRef.value
  if (!viewport) {
    return
  }

  const rect = viewport.getBoundingClientRect()
  const pointerX = clientX - rect.left
  const pointerY = clientY - rect.top

  const previousScale = scale.value
  const nextScale = clampScale(previousScale * (1 - delta * 0.001))

  if (nextScale === previousScale) {
    return
  }

  const imageX = (pointerX - translateX.value) / previousScale
  const imageY = (pointerY - translateY.value) / previousScale

  translateX.value = pointerX - imageX * nextScale
  translateY.value = pointerY - imageY * nextScale
  scale.value = nextScale
}

function onWheel(event: WheelEvent): void {
  event.preventDefault()

  if (event.ctrlKey || event.metaKey) {
    zoomAt(event.clientX, event.clientY, event.deltaY)
    return
  }

  if (event.deltaMode === WheelEvent.DOM_DELTA_PIXEL) {
    translateX.value -= event.deltaX
    translateY.value -= event.deltaY
    return
  }

  zoomAt(event.clientX, event.clientY, event.deltaY)
}

function onPointerDown(event: PointerEvent): void {
  if (props.annotationMode && event.button === 0) {
    const point = clientToImagePoint(event.clientX, event.clientY)

    if (!point) {
      return
    }

    event.preventDefault()

    const hitMark = findEditorMarkAtPoint(point, props.marks, imageWidth.value, imageHeight.value)

    if (hitMark) {
      isMovingMark.value = true
      movingMarkId.value = hitMark.id
      movePointerId.value = event.pointerId
      moveStartCenterX.value = hitMark.centerX * imageWidth.value
      moveStartCenterY.value = hitMark.centerY * imageHeight.value
      moveStartPointerX.value = point.x
      moveStartPointerY.value = point.y
      movingMarkCenterPx.value = {
        x: moveStartCenterX.value,
        y: moveStartCenterY.value,
      }
      hoveredMarkId.value = hitMark.id
      viewportRef.value?.setPointerCapture?.(event.pointerId)
      return
    }

    isDrawing.value = true
    drawPointerId.value = event.pointerId
    drawStartX.value = point.x
    drawStartY.value = point.y
    drawCurrentX.value = point.x
    drawCurrentY.value = point.y
    hoveredMarkId.value = null

    viewportRef.value?.setPointerCapture?.(event.pointerId)
    return
  }

  if (event.button !== 0 && event.button !== 1) {
    return
  }

  event.preventDefault()

  isPanning.value = true
  panPointerId = event.pointerId
  panStartX = event.clientX
  panStartY = event.clientY
  panStartTranslateX = translateX.value
  panStartTranslateY = translateY.value

  viewportRef.value?.setPointerCapture?.(event.pointerId)
}

function onPointerMove(event: PointerEvent): void {
  const point = clientToImagePoint(event.clientX, event.clientY)

  if (isDrawing.value && event.pointerId === drawPointerId.value) {
    if (point) {
      drawCurrentX.value = point.x
      drawCurrentY.value = point.y
    }

    return
  }

  if (isMovingMark.value && event.pointerId === movePointerId.value && point) {
    movingMarkCenterPx.value = {
      x: moveStartCenterX.value + (point.x - moveStartPointerX.value),
      y: moveStartCenterY.value + (point.y - moveStartPointerY.value),
    }
    return
  }

  if (props.annotationMode) {
    updateHoveredMark(point)
  }

  if (!isPanning.value || event.pointerId !== panPointerId) {
    return
  }

  translateX.value = panStartTranslateX + (event.clientX - panStartX)
  translateY.value = panStartTranslateY + (event.clientY - panStartY)
}

function endPan(event: PointerEvent): void {
  if (isDrawing.value && event.pointerId === drawPointerId.value) {
    finishDrawing()

    if (viewportRef.value?.hasPointerCapture?.(event.pointerId)) {
      viewportRef.value.releasePointerCapture(event.pointerId)
    }

    updateHoveredMark(clientToImagePoint(event.clientX, event.clientY))
    return
  }

  if (isMovingMark.value && event.pointerId === movePointerId.value) {
    finishMovingMark(event)

    if (viewportRef.value?.hasPointerCapture?.(event.pointerId)) {
      viewportRef.value.releasePointerCapture(event.pointerId)
    }

    return
  }

  if (!isPanning.value || event.pointerId !== panPointerId) {
    return
  }

  isPanning.value = false
  panPointerId = null

  if (viewportRef.value?.hasPointerCapture?.(event.pointerId)) {
    viewportRef.value.releasePointerCapture(event.pointerId)
  }
}

function onAuxClick(event: MouseEvent): void {
  if (event.button === 1) {
    event.preventDefault()
  }
}

function onImageLoad(): void {
  if (imageRef.value) {
    loadedImageWidth.value = imageRef.value.naturalWidth
    loadedImageHeight.value = imageRef.value.naturalHeight
  }

  fitImageToViewport()
}

watch(
  () => props.src,
  () => {
    scale.value = 1
    translateX.value = 0
    translateY.value = 0
    loadedImageWidth.value = 0
    loadedImageHeight.value = 0
    hoveredMarkId.value = null
    finishMovingMark()
    isDrawing.value = false
    drawPointerId.value = null
  },
)

watch(
  () => props.annotationMode,
  (enabled) => {
    if (!enabled) {
      hoveredMarkId.value = null
      finishMovingMark()
      isDrawing.value = false
      drawPointerId.value = null
    }
  },
)

watch(
  () => props.marks,
  (marks) => {
    if (marks.length > 0) {
      return
    }

    hoveredMarkId.value = null
    isMovingMark.value = false
    movingMarkId.value = null
    movePointerId.value = null
    movingMarkCenterPx.value = null
    isDrawing.value = false
    drawPointerId.value = null
  },
)

defineExpose({
  fitImageToViewport,
})
</script>

<template>
  <div class="relative h-full w-full">
    <div
      ref="viewportRef"
      data-testid="image-viewport"
      class="absolute inset-0 touch-none overflow-hidden select-none"
      :class="viewportCursor"
      @wheel.prevent="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="endPan"
      @pointercancel="endPan"
      @auxclick="onAuxClick"
    >
      <div class="absolute inset-0" :style="contentStyle">
      <img
        ref="imageRef"
        :src="src"
        :alt="alt"
        draggable="false"
        class="block max-w-none"
        @load="onImageLoad"
        @dragstart.prevent
      />

      <svg
        v-if="showAnnotationOverlay"
        class="pointer-events-none absolute left-0 top-0"
        :width="imageWidth"
        :height="imageHeight"
        :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
      >
        <g v-for="(mark, index) in displayMarks" :key="mark.id">
          <circle
            :cx="mark.centerX * imageWidth"
            :cy="mark.centerY * imageHeight"
            :r="mark.radius * imageBase"
            fill="none"
            stroke="#FF3B30"
            :stroke-width="strokeWidth"
            :opacity="movingMarkId === mark.id || hoveredMarkId === mark.id ? 1 : 0.92"
          />
          <circle
            :cx="mark.centerX * imageWidth + mark.radius * imageBase * 0.65"
            :cy="mark.centerY * imageHeight - mark.radius * imageBase * 0.65"
            :r="Math.max(10, imageBase * 0.025)"
            fill="#FF3B30"
          />
          <text
            :x="mark.centerX * imageWidth + mark.radius * imageBase * 0.65"
            :y="mark.centerY * imageHeight - mark.radius * imageBase * 0.65"
            fill="#FFFFFF"
            text-anchor="middle"
            dominant-baseline="middle"
            :font-size="Math.max(14, imageBase * 0.035)"
            font-weight="700"
          >
            {{ index + 1 }}
          </text>
        </g>

        <g v-if="drawingPreview">
          <line
            :x1="drawingPreview.startX"
            :y1="drawingPreview.startY"
            :x2="drawingPreview.currentX"
            :y2="drawingPreview.currentY"
            stroke="#FF3B30"
            :stroke-width="strokeWidth"
            stroke-linecap="round"
          />
          <circle
            :cx="drawingPreview.startX"
            :cy="drawingPreview.startY"
            :r="Math.max(3, strokeWidth * 0.75)"
            fill="#FF3B30"
          />
          <circle
            v-if="drawingPreview.radius >= 1"
            :cx="drawingPreview.startX"
            :cy="drawingPreview.startY"
            :r="drawingPreview.radius"
            fill="rgba(255, 59, 48, 0.08)"
            stroke="#FF3B30"
            :stroke-width="strokeWidth"
            stroke-dasharray="6 4"
          />
        </g>
      </svg>
      </div>
    </div>

    <button
      type="button"
      class="absolute bottom-3 right-3 z-10 inline-flex size-8 cursor-pointer items-center justify-center rounded-md border border-app-border bg-app/90 text-app-muted shadow-sm backdrop-blur-sm transition hover:bg-app-elevated hover:text-app-foreground"
      :aria-label="t('workspace.fitCanvas')"
      :title="t('workspace.fitCanvas')"
      @click="fitImageToViewport"
    >
      <Maximize2 :size="16" :stroke-width="1.75" />
    </button>
  </div>
</template>
