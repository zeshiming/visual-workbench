<script setup lang="ts">
import { Download, LoaderCircle, Sparkles, Trash2, Wand2 } from '@lucide/vue'
import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  getDeficiencyCategoryLabel,
  getDeficiencySeverityLabel,
  getImageTypeLabel,
} from '@/lib/agent-labels'
import { listModelsByRole } from '@/lib/app-settings'
import ModelSelect from '@/components/ModelSelect.vue'
import { loadAppSettings } from '@/lib/config-storage'
import { exportWorkspaceImage } from '@/lib/export-workspace-image'
import { runWorkspaceAgent } from '@/lib/run-workspace-agent'
import { runWorkspaceEditor } from '@/lib/run-workspace-editor'
import {
  assetImageUrl,
  listWorkspaceAssets,
  uploadWorkspaceAsset,
} from '@/lib/api-client'
import { readImageFileAsDataUrl } from '@/lib/read-image-file'
import {
  applyBasicImageAdjustments,
  applyCubeLut,
  applyReferenceColorTransfer,
  DEFAULT_IMAGE_ADJUSTMENTS,
  computeLuminanceHistogram,
  estimateAutoWhiteBalance,
  loadAdjustmentSource,
  parseCubeLut,
  renderBasicImageAdjustments,
  STYLE_PRESETS,
  type StylePresetId,
  type BasicImageAdjustments,
} from '@/lib/image-adjustments'
import {
  getWorkspace,
  getWorkspaceImageRevision,
  openWorkspaces,
  recordWorkspaceImageHistory,
  stageWorkspaceImageChange,
  setWorkspaceEditing,
  applyWorkspaceGeneratedImage,
} from '@/lib/workspace-session'
import { loadWorkspaceImage } from '@/lib/workspace-image-storage'
import {
  clearWorkspaceRunPresentation,
  getWorkspaceAgentPrompt,
  getWorkspaceAnalysis,
  getWorkspaceEditMode,
  getWorkspaceEditorMarks,
  getWorkspaceModelSelection,
  getWorkspaceRunError,
  getWorkspaceRunStep,
  getWorkspaceSelectedAnalysisModelId,
  getWorkspaceSelectedEditModelId,
  isWorkspaceRunning,
  setWorkspaceAgentPrompt,
  setWorkspaceAnalysis,
  setWorkspaceEditMode,
  setWorkspaceEditorMarks,
  setWorkspaceRunError,
  setWorkspaceRunStep,
  setWorkspaceSelectedAnalysisModelId,
  setWorkspaceSelectedEditModelId,
  workspaceUiRevision,
  clearWorkspaceEditorMarks,
  getWorkspaceSelectedAssetIds,
  getWorkspaceActiveAssetId,
  getWorkspaceAssetAdjustments,
  notifyWorkspaceAssetsChanged,
  setWorkspaceAssetAdjustments,
} from '@/lib/workspace-ui-state'
import type { EditorMark } from '@/types/editor-mark'
import type { WorkspaceMode } from '@/types/workspace-mode'

const props = withDefaults(
  defineProps<{
    activeWorkspaceId: string
    workspaceMode?: WorkspaceMode
  }>(),
  { workspaceMode: 'ai' as WorkspaceMode },
)

const { t } = useI18n()

const isExporting = ref(false)
const exportError = ref('')
const adjustmentImage = ref<string | null>(null)
const adjustmentBaseImage = ref<string | null>(null)
const adjustmentError = ref('')
const adjustmentBusy = ref(false)
const adjustmentHistoryRecorded = ref(false)
const adjustmentFullSource = shallowRef<HTMLImageElement | null>(null)
const histogram = ref<number[]>([])
const batchBusy = ref(false)
const batchProgress = ref(0)
const batchTotal = ref(0)
const batchError = ref('')
const referencePicker = ref<HTMLInputElement | null>(null)
const referenceName = ref('')
const referenceSource = shallowRef<HTMLImageElement | null>(null)
const lutPicker = ref<HTMLInputElement | null>(null)
const lutName = ref('')
const adjustments = reactive<BasicImageAdjustments>({ ...DEFAULT_IMAGE_ADJUSTMENTS })

const adjustmentItems = [
  { key: 'exposure' as const, label: '曝光', min: -100, max: 100 },
  { key: 'contrast' as const, label: '对比度', min: -100, max: 100 },
  { key: 'highlights' as const, label: '高光', min: -100, max: 100 },
  { key: 'shadows' as const, label: '阴影', min: -100, max: 100 },
  { key: 'saturation' as const, label: '饱和度', min: -100, max: 100 },
  { key: 'temperature' as const, label: '色温', min: -100, max: 100 },
  { key: 'tint' as const, label: '色调', min: -100, max: 100 },
]

const modeOptions = [
  { value: 'agent' as const, label: 'Agent' },
  { value: 'editor' as const, label: 'Editor' },
]

const workspace = computed(() => {
  openWorkspaces.value

  if (!props.activeWorkspaceId) {
    return null
  }

  return getWorkspace(props.activeWorkspaceId)
})

const editMode = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return 'agent' as const
  }

  return getWorkspaceEditMode(props.activeWorkspaceId)
})

const editorMarks = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return [] as EditorMark[]
  }

  return getWorkspaceEditorMarks(props.activeWorkspaceId)
})

const agentPrompt = computed({
  get() {
    workspaceUiRevision.value

    if (!props.activeWorkspaceId) {
      return ''
    }

    return getWorkspaceAgentPrompt(props.activeWorkspaceId)
  },
  set(value: string) {
    if (!props.activeWorkspaceId) {
      return
    }

    setWorkspaceAgentPrompt(props.activeWorkspaceId, value)
  },
})

const hasImage = computed(
  () => Boolean(workspace.value?.sourceImage || workspace.value?.hasSourceImage),
)

const activeAssetId = computed(() => {
  workspaceUiRevision.value
  return props.activeWorkspaceId ? getWorkspaceActiveAssetId(props.activeWorkspaceId) : null
})

const selectedAssetCount = computed(() => {
  workspaceUiRevision.value
  return props.activeWorkspaceId
    ? getWorkspaceSelectedAssetIds(props.activeWorkspaceId).length
    : 0
})

async function loadAdjustmentImage(workspaceId: string): Promise<void> {
  const current = getWorkspace(workspaceId)
  const image = current?.sourceImage
    ?? (current?.hasSourceImage ? await loadWorkspaceImage(workspaceId) : null)

  adjustmentImage.value = image
  adjustmentBaseImage.value = image
  adjustmentFullSource.value = image ? await loadAdjustmentSource(image) : null
  histogram.value = adjustmentFullSource.value
    ? computeLuminanceHistogram(adjustmentFullSource.value)
    : []
  adjustmentHistoryRecorded.value = false
  Object.assign(
    adjustments,
    getWorkspaceAssetAdjustments(workspaceId, activeAssetId.value, DEFAULT_IMAGE_ADJUSTMENTS),
  )
}

function ensureAdjustmentHistory(): boolean {
  const workspaceId = props.activeWorkspaceId
  const current = workspaceId ? getWorkspace(workspaceId) : null
  const baseImage = adjustmentBaseImage.value

  if (!workspaceId || !current || !baseImage || isWorkspaceRunning(workspaceId)) {
    return false
  }

  if (!adjustmentHistoryRecorded.value) {
    recordWorkspaceImageHistory(workspaceId, current.sourceImage ?? baseImage)
    adjustmentHistoryRecorded.value = true
  }

  return true
}

function stageAdjustmentResult(nextImage: string): void {
  const workspaceId = props.activeWorkspaceId
  const current = workspaceId ? getWorkspace(workspaceId) : null
  if (!workspaceId || !current) return

  stageWorkspaceImageChange({
    ...current,
    sourceImage: nextImage,
    hasSourceImage: true,
    updatedAt: Date.now(),
  })
  adjustmentImage.value = nextImage
}

function handleAdjustmentInput(): void {
  if (!ensureAdjustmentHistory()) return
  if (props.activeWorkspaceId) {
    setWorkspaceAssetAdjustments(props.activeWorkspaceId, activeAssetId.value, adjustments)
  }
  // Keep the current full-resolution image in the viewport while dragging.
  // The rendered result is committed by the slider's change event.
  adjustmentBusy.value = false
  adjustmentError.value = ''
}

function handleAdjustmentCommit(): void {
  if (!ensureAdjustmentHistory() || !adjustmentFullSource.value) return
  if (props.activeWorkspaceId) {
    setWorkspaceAssetAdjustments(props.activeWorkspaceId, activeAssetId.value, adjustments)
  }

  adjustmentBusy.value = true
  try {
    stageAdjustmentResult(renderBasicImageAdjustments(adjustmentFullSource.value, adjustments))
  } catch (err) {
    adjustmentError.value = err instanceof Error ? err.message : '调色失败'
  } finally {
    adjustmentBusy.value = false
  }
}

function handleAutoWhiteBalance(): void {
  if (!adjustmentFullSource.value || !ensureAdjustmentHistory()) return

  try {
    const estimate = estimateAutoWhiteBalance(adjustmentFullSource.value)
    adjustments.temperature = estimate.temperature
    adjustments.tint = estimate.tint
    handleAdjustmentCommit()
  } catch (err) {
    adjustmentError.value = err instanceof Error ? err.message : '自动白平衡失败'
  }
}

function applyStylePreset(presetId: StylePresetId): void {
  const preset = STYLE_PRESETS.find((item) => item.id === presetId)
  if (!preset || !ensureAdjustmentHistory()) return
  Object.assign(adjustments, preset.adjustments)
  handleAdjustmentCommit()
}

function openReferencePicker(): void {
  referencePicker.value?.click()
}

async function handleReferencePick(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !adjustmentFullSource.value || !ensureAdjustmentHistory()) return

  try {
    const reference = await loadAdjustmentSource(await readImageFileAsDataUrl(file))
    referenceSource.value = reference
    stageAdjustmentResult(applyReferenceColorTransfer(adjustmentFullSource.value, reference))
    referenceName.value = file.name
  } catch (err) {
    adjustmentError.value = err instanceof Error ? err.message : '追色失败'
  }
}

function applyReferenceToCurrent(): void {
  if (!referenceSource.value || !adjustmentFullSource.value || !ensureAdjustmentHistory()) return
  try {
    stageAdjustmentResult(applyReferenceColorTransfer(adjustmentFullSource.value, referenceSource.value))
  } catch (err) {
    adjustmentError.value = err instanceof Error ? err.message : '追色失败'
  }
}

function openLutPicker(): void {
  lutPicker.value?.click()
}

async function handleLutPick(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !adjustmentFullSource.value || !ensureAdjustmentHistory()) return

  try {
    const lut = parseCubeLut(await file.text())
    stageAdjustmentResult(applyCubeLut(adjustmentFullSource.value, lut))
    lutName.value = file.name
  } catch (err) {
    adjustmentError.value = err instanceof Error ? err.message : 'LUT 应用失败'
  }
}

async function handleBatchAdjustments(mode: 'adjustments' | 'whiteBalance' | 'reference' = 'adjustments'): Promise<void> {
  const workspaceId = props.activeWorkspaceId
  if (!workspaceId || batchBusy.value || selectedAssetCount.value === 0) return

  batchBusy.value = true
  batchError.value = ''
  batchProgress.value = 0

  try {
    const selectedIds = new Set(getWorkspaceSelectedAssetIds(workspaceId))
    const assets = (await listWorkspaceAssets(workspaceId)).filter((asset) => selectedIds.has(asset.id))
    batchTotal.value = assets.length
    const failures: string[] = []

    for (const asset of assets) {
      try {
        const response = await fetch(assetImageUrl(workspaceId, asset.id))
        if (!response.ok) throw new Error('读取原图失败')
        const sourceFile = new File(
          [await response.blob()],
          asset.filename,
          { type: asset.mediaType },
        )
        const source = await readImageFileAsDataUrl(sourceFile)
        let adjusted: string
        const batchAdjustments = { ...adjustments }
        if (mode === 'whiteBalance') {
          const sourceForAnalysis = await loadAdjustmentSource(source)
          Object.assign(batchAdjustments, estimateAutoWhiteBalance(sourceForAnalysis))
          adjusted = await applyBasicImageAdjustments(source, batchAdjustments)
        } else if (mode === 'reference' && referenceSource.value) {
          adjusted = applyReferenceColorTransfer(
            await loadAdjustmentSource(source),
            referenceSource.value,
          )
        } else {
          adjusted = await applyBasicImageAdjustments(source, batchAdjustments)
        }
        const adjustedBlob = await (await fetch(adjusted)).blob()
        const baseName = asset.filename.replace(/\.[^.]+$/, '')
        const output = new File([adjustedBlob], `${baseName}-调色.png`, { type: 'image/png' })
        await uploadWorkspaceAsset(workspaceId, output, 'edit')
      } catch {
        failures.push(asset.filename)
      } finally {
        batchProgress.value += 1
      }
    }

    if (failures.length) {
      batchError.value = `${failures.length} 张照片处理失败：${failures.slice(0, 2).join('、')}`
    }
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '批量调色失败'
  } finally {
    batchBusy.value = false
  }
}

function handleBatchAutoWhiteBalance(): void {
  void handleBatchAdjustments('whiteBalance')
}

function handleBatchReferenceColor(): void {
  void handleBatchAdjustments('reference')
}

function resetAdjustments(): void {
  if (!adjustmentBaseImage.value || !props.activeWorkspaceId) return
  const current = getWorkspace(props.activeWorkspaceId)

  if (current && adjustmentImage.value !== adjustmentBaseImage.value) {
    stageWorkspaceImageChange({
      ...current,
      sourceImage: adjustmentBaseImage.value,
      hasSourceImage: true,
      updatedAt: Date.now(),
    })
    adjustmentImage.value = adjustmentBaseImage.value
  }

  Object.assign(adjustments, DEFAULT_IMAGE_ADJUSTMENTS)
  if (props.activeWorkspaceId) {
    setWorkspaceAssetAdjustments(props.activeWorkspaceId, activeAssetId.value, adjustments)
  }
  adjustmentError.value = ''
}

watch(
  () => [props.activeWorkspaceId, activeAssetId.value] as const,
  (workspaceId) => {
    if (workspaceId) {
      void loadAdjustmentImage(workspaceId)
      return
    }

    adjustmentImage.value = null
    adjustmentBaseImage.value = null
  },
  { immediate: true },
)

// A workspace opened from storage may hydrate its image after this sidebar
// has mounted. Retry once the workspace reports that an image is available.
watch(
  () => [
    props.activeWorkspaceId,
    workspace.value?.sourceImage,
    workspace.value?.hasSourceImage,
  ] as const,
  ([workspaceId]) => {
    if (workspaceId && hasImage.value && !adjustmentImage.value) {
      void loadAdjustmentImage(workspaceId)
    }
  },
  { immediate: true },
)

const isRunning = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return false
  }

  return isWorkspaceRunning(props.activeWorkspaceId)
})

const runStep = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return null
  }

  return getWorkspaceRunStep(props.activeWorkspaceId)
})

const error = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return ''
  }

  return getWorkspaceRunError(props.activeWorkspaceId)
})

const analysis = computed(() => {
  workspaceUiRevision.value

  if (!props.activeWorkspaceId) {
    return null
  }

  return getWorkspaceAnalysis(props.activeWorkspaceId)
})

const appSettings = computed(() => {
  workspaceUiRevision.value
  return loadAppSettings()
})

const analysisModels = computed(() => listModelsByRole(appSettings.value, 'analysis'))
const editModels = computed(() => listModelsByRole(appSettings.value, 'edit'))

const selectedAnalysisModelId = computed({
  get() {
    workspaceUiRevision.value

    if (!props.activeWorkspaceId) {
      return ''
    }

    return (
      getWorkspaceSelectedAnalysisModelId(props.activeWorkspaceId)
      ?? appSettings.value.defaultAnalysisModelId
    )
  },
  set(value: string) {
    if (!props.activeWorkspaceId) {
      return
    }

    setWorkspaceSelectedAnalysisModelId(
      props.activeWorkspaceId,
      value === appSettings.value.defaultAnalysisModelId ? null : value,
    )
  },
})

const selectedEditModelId = computed({
  get() {
    workspaceUiRevision.value

    if (!props.activeWorkspaceId) {
      return ''
    }

    return (
      getWorkspaceSelectedEditModelId(props.activeWorkspaceId)
      ?? appSettings.value.defaultEditModelId
    )
  },
  set(value: string) {
    if (!props.activeWorkspaceId) {
      return
    }

    setWorkspaceSelectedEditModelId(
      props.activeWorkspaceId,
      value === appSettings.value.defaultEditModelId ? null : value,
    )
  },
})

const runStatusText = computed(() => {
  if (runStep.value === 'analysis') {
    return t('editorPanel.analyzing')
  }

  if (runStep.value === 'edit') {
    return editMode.value === 'editor' ? t('editorPanel.editingByMarks') : t('editorPanel.editing')
  }

  return ''
})

function setEditMode(mode: 'agent' | 'editor') {
  if (!props.activeWorkspaceId || isWorkspaceRunning(props.activeWorkspaceId)) {
    return
  }

  setWorkspaceEditMode(props.activeWorkspaceId, mode)
}

function updateMarkDescription(markId: string, description: string) {
  if (!props.activeWorkspaceId) {
    return
  }

  const nextMarks = editorMarks.value.map((mark) =>
    mark.id === markId ? { ...mark, description } : mark,
  )

  setWorkspaceEditorMarks(props.activeWorkspaceId, nextMarks)
}

function removeMark(markId: string) {
  if (!props.activeWorkspaceId || isWorkspaceRunning(props.activeWorkspaceId)) {
    return
  }

  setWorkspaceEditorMarks(
    props.activeWorkspaceId,
    editorMarks.value.filter((mark) => mark.id !== markId),
  )
}

watch(
  () =>
    props.activeWorkspaceId
      ? getWorkspaceImageRevision(props.activeWorkspaceId)
      : 0,
  () => {
    if (!props.activeWorkspaceId || isWorkspaceRunning(props.activeWorkspaceId)) {
      return
    }

    clearWorkspaceRunPresentation(props.activeWorkspaceId)
  },
)

async function handleExportImage() {
  const currentWorkspace = workspace.value

  if (!currentWorkspace || isExporting.value) {
    return
  }

  isExporting.value = true
  exportError.value = ''

  try {
    await exportWorkspaceImage(currentWorkspace)
  } catch (err) {
    exportError.value = err instanceof Error ? err.message : t('errors.exportFailed')
  } finally {
    isExporting.value = false
  }
}

async function handleAgentRun() {
  const currentWorkspace = workspace.value
  const workspaceId = currentWorkspace?.id

  if (!currentWorkspace || !workspaceId || isWorkspaceRunning(workspaceId)) {
    return
  }

  const prompt = getWorkspaceAgentPrompt(workspaceId)

  setWorkspaceRunStep(workspaceId, 'analysis')
  setWorkspaceRunError(workspaceId, '')
  setWorkspaceAnalysis(workspaceId, null)
  setWorkspaceEditing(workspaceId, true)

  try {
    const result = await runWorkspaceAgent(currentWorkspace, prompt, {
      onProgress: (step) => {
        setWorkspaceRunStep(workspaceId, step)
      },
      modelSelection: getWorkspaceModelSelection(workspaceId),
    })
    setWorkspaceAnalysis(workspaceId, result.analysis)

    const nextImage = result.images[0]
    if (!nextImage) {
      throw new Error(t('errors.editModelNoImage'))
    }

    await applyWorkspaceGeneratedImage(currentWorkspace, nextImage)
  } catch (err) {
    setWorkspaceRunError(workspaceId, err instanceof Error ? err.message : t('errors.agentFailed'))
  } finally {
    setWorkspaceEditing(workspaceId, false)
    setWorkspaceRunStep(workspaceId, null)
  }
}

async function handleEditorRun() {
  const currentWorkspace = workspace.value
  const workspaceId = currentWorkspace?.id

  if (!currentWorkspace || !workspaceId || isWorkspaceRunning(workspaceId)) {
    return
  }

  const marks = getWorkspaceEditorMarks(workspaceId)

  setWorkspaceRunStep(workspaceId, 'edit')
  setWorkspaceRunError(workspaceId, '')
  setWorkspaceEditing(workspaceId, true)

  let succeeded = false

  try {
    const nextImage = await runWorkspaceEditor(
      currentWorkspace,
      marks,
      getWorkspaceModelSelection(workspaceId),
    )
    await applyWorkspaceGeneratedImage(currentWorkspace, nextImage)
    succeeded = true
  } catch (err) {
    setWorkspaceRunError(workspaceId, err instanceof Error ? err.message : t('errors.editorFailed'))
  } finally {
    setWorkspaceEditing(workspaceId, false)
    setWorkspaceRunStep(workspaceId, null)

    if (succeeded) {
      clearWorkspaceEditorMarks(workspaceId)
    }
  }
}

const inputClass = 'app-field resize-none'
</script>

<template>
  <aside
    class="app-right-sidebar flex w-64 shrink-0 flex-col border-l border-app-border bg-app"
    :aria-label="t('editorPanel.title')"
  >
    <div class="app-right-sidebar-header border-b border-app-border px-3 py-2.5">
      <div class="flex items-center justify-between gap-2">
        <div>
          <div class="app-eyebrow">AI TOOLKIT</div>
          <h2 class="mt-1 text-sm font-medium tracking-tight text-app-foreground">
          {{ t('editorPanel.title') }}
          </h2>
        </div>
        <div
          v-if="workspaceMode === 'ai'"
          class="app-segmented"
          role="tablist"
          :aria-label="t('editorPanel.modeLabel')"
        >
          <button
            v-for="option in modeOptions"
            :key="option.value"
            type="button"
            role="tab"
            class="app-segmented-item"
            :class="editMode === option.value ? 'app-segmented-item-active' : 'app-segmented-item-inactive'"
            :aria-selected="editMode === option.value"
            :disabled="isRunning"
            @click="setEditMode(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </div>

    <div class="app-panel-body">
      <p v-if="!activeWorkspaceId" class="px-1 py-6 text-center text-xs text-app-subtle">
        {{ t('editorPanel.noWorkspace') }}
      </p>

      <p v-else-if="!hasImage" class="px-1 py-6 text-center text-xs text-app-subtle">
        {{ t('editorPanel.uploadFirst') }}
      </p>

      <div v-else class="flex min-h-0 flex-1 flex-col gap-3">
        <section v-if="workspaceMode === 'photos'" class="app-card space-y-3 p-3">
          <div class="app-eyebrow">PHOTO LIBRARY</div>
          <h3 class="text-sm font-medium text-app-foreground">照片选择</h3>
          <p class="text-xs leading-relaxed text-app-muted">在中央联系表中导入照片、输入客户编号、筛选 JPG / RAW，并勾选要处理的照片。</p>
          <div class="app-card px-3 py-2.5">
            <div class="flex items-center justify-between gap-2 text-xs">
              <span class="text-app-muted">当前已选</span>
              <span class="font-medium text-app-primary">{{ selectedAssetCount }} 张</span>
            </div>
          </div>
        </section>

        <section v-if="workspaceMode === 'match' && hasImage" class="app-card space-y-3 p-3">
          <div class="app-eyebrow">REFERENCE COLOR MATCH</div>
          <h3 class="text-sm font-medium text-app-foreground">参考图追色</h3>
          <p class="text-xs leading-relaxed text-app-muted">导入一张参考照片，使用颜色均值和通道标准差迁移到当前照片或已选照片。</p>
          <input ref="referencePicker" class="hidden" type="file" accept="image/jpeg,image/png,image/webp" @change="handleReferencePick" />
          <button type="button" class="app-btn-secondary w-full" :disabled="batchBusy || isRunning" @click="openReferencePicker">
            <Download :size="14" :stroke-width="1.8" />
            {{ referenceName ? `参考图：${referenceName}` : '导入参考图' }}
          </button>
          <button v-if="referenceSource" type="button" class="app-btn-primary w-full" :disabled="batchBusy || isRunning" @click="applyReferenceToCurrent">
            当前照片应用追色
          </button>
          <button v-if="referenceSource && selectedAssetCount" type="button" class="app-btn-secondary w-full" :disabled="batchBusy || isRunning" @click="handleBatchReferenceColor">
            批量追色（{{ selectedAssetCount }} 张）
          </button>
        </section>

        <section v-if="workspaceMode === 'styles' && hasImage" class="app-card space-y-3 p-3">
          <div class="app-eyebrow">STYLE / LUT</div>
          <h3 class="text-sm font-medium text-app-foreground">风格化</h3>
          <div class="grid grid-cols-2 gap-1.5">
            <button v-for="preset in STYLE_PRESETS" :key="preset.id" type="button" class="app-preset-button" :disabled="adjustmentBusy || batchBusy || isRunning" @click="applyStylePreset(preset.id)">{{ preset.label }}</button>
          </div>
          <input ref="lutPicker" class="hidden" type="file" accept=".cube,text/plain" @change="handleLutPick" />
          <button type="button" class="app-btn-secondary w-full" :disabled="adjustmentBusy || batchBusy || isRunning" @click="openLutPicker">
            <Download :size="14" :stroke-width="1.8" />
            {{ lutName ? `LUT：${lutName}` : '导入 .cube LUT' }}
          </button>
        </section>

        <section v-if="workspaceMode === 'develop' && hasImage" class="app-card app-basic-adjustments space-y-3 p-3">
          <template v-if="adjustmentImage">
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="app-eyebrow">LOCAL PROCESSING</div>
              <h3 class="mt-1 text-sm font-medium text-app-foreground">基础调色</h3>
            </div>
            <button type="button" class="app-btn-quiet" :disabled="adjustmentBusy" @click="resetAdjustments">重置</button>
          </div>
          <p class="text-[11px] leading-relaxed text-app-subtle">在浏览器本地处理，不调用 AI。松开滑杆后更新预览。</p>
          <button
            type="button"
            class="app-btn-secondary w-full"
            :disabled="adjustmentBusy || batchBusy || isRunning"
            @click="handleAutoWhiteBalance"
          >
            <Wand2 :size="14" :stroke-width="1.8" />
            自动白平衡
          </button>
          <div v-if="histogram.length" class="app-histogram" aria-label="亮度直方图">
            <span v-for="(value, index) in histogram" :key="index" :style="{ height: `${Math.max(4, value * 100)}%` }" />
          </div>
          <label v-for="item in adjustmentItems" :key="item.key" class="app-adjustment-row">
            <span class="flex items-center justify-between gap-2 text-xs text-app-muted">
              <span>{{ item.label }}</span>
              <output>{{ adjustments[item.key] }}</output>
            </span>
            <input
              v-model.number="adjustments[item.key]"
              type="range"
              :min="item.min"
              :max="item.max"
              step="1"
              :aria-label="item.label"
              :disabled="isRunning"
              @input="handleAdjustmentInput"
              @change="handleAdjustmentCommit"
            />
          </label>
          <div v-if="selectedAssetCount" class="border-t border-app-border pt-3">
            <button
              type="button"
              class="app-btn-primary w-full"
              :disabled="batchBusy || isRunning"
              @click="handleBatchAdjustments"
            >
              <LoaderCircle v-if="batchBusy" :size="14" :stroke-width="1.8" class="animate-spin" />
              <Wand2 v-else :size="14" :stroke-width="1.8" />
              {{ batchBusy ? `正在处理 ${batchProgress}/${batchTotal}` : `应用到已选 ${selectedAssetCount} 张` }}
            </button>
            <button
              type="button"
              class="app-btn-secondary mt-2 w-full"
              :disabled="batchBusy || isRunning"
              @click="handleBatchAutoWhiteBalance"
            >
              <Wand2 :size="14" :stroke-width="1.8" />
              批量自动白平衡
            </button>
            <p class="mt-1.5 text-[10px] text-app-subtle">原图保留，结果将作为新的编辑版本加入照片库。</p>
          </div>
          <p v-if="adjustmentBusy" class="text-[11px] text-app-muted">正在更新完整预览…</p>
          <p v-if="adjustmentError" class="text-[11px] text-red-400">{{ adjustmentError }}</p>
          <p v-if="batchError" class="text-[11px] text-red-400">{{ batchError }}</p>
          </template>
          <p v-else class="text-[11px] text-app-subtle">正在加载基础调色…</p>
        </section>

        <div v-if="workspaceMode === 'ai' && editMode === 'editor'" class="flex flex-col gap-3">
        <p class="text-xs leading-relaxed text-app-muted">
          {{ t('editorPanel.editorHint') }}
        </p>

        <section v-if="editorMarks.length" class="space-y-2">
          <h3 class="text-xs font-medium text-app-muted uppercase">{{ t('editorPanel.annotationAreas') }}</h3>
          <div
            v-for="(mark, index) in editorMarks"
            :key="mark.id"
            class="app-card p-2.5"
          >
            <div class="mb-1.5 flex items-center justify-between gap-2">
              <span class="text-xs font-medium text-app-foreground">{{ t('editorPanel.circleLabel', { number: index + 1 }) }}</span>
              <button
                type="button"
                class="rounded p-1 text-app-muted transition hover:bg-app-surface hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="isRunning"
                :aria-label="t('editorPanel.deleteAnnotation')"
                @click="removeMark(mark.id)"
              >
                <Trash2 :size="13" :stroke-width="1.75" />
              </button>
            </div>
            <textarea
              :value="mark.description"
              rows="2"
              :placeholder="t('editorPanel.markPlaceholder')"
              :class="inputClass"
              :disabled="isRunning"
              @input="updateMarkDescription(mark.id, ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
        </section>

        <p v-else class="app-card border-dashed px-3 py-4 text-center text-xs text-app-subtle">
          {{ t('editorPanel.noAnnotations') }}
        </p>

        <label class="block space-y-1.5">
          <span class="text-xs font-medium text-app-muted">{{ t('editorPanel.editModel') }}</span>
          <ModelSelect
            v-model="selectedEditModelId"
            :settings="appSettings"
            :models="editModels"
            :disabled="isRunning"
            :placeholder="t('settings.selectEditModel')"
          />
        </label>

        <button
          type="button"
          class="app-btn-primary w-full"
          :disabled="isRunning || editorMarks.length === 0"
          @click="handleEditorRun"
        >
          <LoaderCircle v-if="isRunning" :size="15" :stroke-width="1.75" class="animate-spin" />
          <Wand2 v-else :size="15" :stroke-width="1.75" />
          {{ isRunning ? t('common.processing') : t('editorPanel.startEdit') }}
        </button>

        <p v-if="runStatusText" class="text-xs text-app-muted">{{ runStatusText }}</p>
        <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>

        <div class="border-t border-app-border pt-3">
          <button
            type="button"
            class="app-btn-secondary w-full"
            :disabled="isExporting || isRunning"
            @click="handleExportImage"
          >
            <LoaderCircle v-if="isExporting" :size="15" :stroke-width="1.75" class="animate-spin" />
            <Download v-else :size="15" :stroke-width="1.75" />
            {{ isExporting ? t('editorPanel.exporting') : t('editorPanel.exportImage') }}
          </button>
          <p v-if="exportError" class="mt-2 text-xs text-red-600 dark:text-red-400">{{ exportError }}</p>
        </div>
      </div>

        <div v-else-if="workspaceMode === 'ai'" class="flex min-h-0 flex-1 flex-col gap-3">
        <p class="text-xs leading-relaxed text-app-muted">
          {{ t('editorPanel.agentHint') }}
        </p>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-app-foreground">{{ t('editorPanel.editRequest') }}</span>
          <textarea
            v-model="agentPrompt"
            rows="6"
            :placeholder="t('editorPanel.editRequestPlaceholder')"
            :class="inputClass"
            :disabled="isRunning"
          />
        </label>

        <div class="app-card space-y-3 p-3">
          <h3 class="text-xs font-medium text-app-muted uppercase">{{ t('editorPanel.runModels') }}</h3>

          <label class="block space-y-1.5">
            <span class="text-xs text-app-muted">{{ t('editorPanel.analysisModel') }}</span>
            <ModelSelect
              v-model="selectedAnalysisModelId"
              :settings="appSettings"
              :models="analysisModels"
              :disabled="isRunning"
              :placeholder="t('settings.selectAnalysisModel')"
            />
          </label>

          <label class="block space-y-1.5">
            <span class="text-xs text-app-muted">{{ t('editorPanel.editModel') }}</span>
            <ModelSelect
              v-model="selectedEditModelId"
              :settings="appSettings"
              :models="editModels"
              :disabled="isRunning"
              :placeholder="t('settings.selectEditModel')"
            />
          </label>
        </div>

        <button
          type="button"
          class="app-btn-primary w-full"
          :disabled="isRunning"
          @click="handleAgentRun"
        >
          <LoaderCircle v-if="isRunning" :size="15" :stroke-width="1.75" class="animate-spin" />
          <Sparkles v-else :size="15" :stroke-width="1.75" />
          {{ isRunning ? t('common.processing') : t('editorPanel.startAgent') }}
        </button>

        <p v-if="runStatusText" class="text-xs text-app-muted">{{ runStatusText }}</p>
        <p v-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</p>

        <section v-if="analysis" class="app-card space-y-3 p-3">
          <div>
            <h3 class="text-xs font-medium text-app-muted uppercase">{{ t('editorPanel.analysisResult') }}</h3>
            <p class="mt-1 text-sm text-app-foreground">
              {{ getImageTypeLabel(analysis.imageType) }}
            </p>
            <p class="mt-1 text-xs text-app-subtle">{{ analysis.imageTypeReason }}</p>
          </div>

          <div>
            <h4 class="text-xs font-medium text-app-muted">{{ t('editorPanel.mainIssues') }}</h4>
            <ul class="mt-2 space-y-2">
              <li
                v-for="(item, index) in analysis.deficiencies"
                :key="`${item.category}-${index}`"
                class="rounded-md border border-app-border bg-app-surface px-2.5 py-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="text-xs font-medium text-app-foreground">
                    {{ getDeficiencyCategoryLabel(item.category) }}
                  </span>
                  <span class="text-[11px] text-app-subtle">
                    {{ getDeficiencySeverityLabel(item.severity) }}
                  </span>
                </div>
                <p class="mt-1 text-xs text-app-muted">{{ item.description }}</p>
              </li>
            </ul>
          </div>

          <p class="text-xs leading-relaxed text-app-muted">{{ analysis.summary }}</p>

          <div>
            <h4 class="text-xs font-medium text-app-muted">{{ t('editorPanel.editInstructions') }}</h4>
            <p class="mt-1 text-xs leading-relaxed text-app-foreground">{{ analysis.editPrompt }}</p>
          </div>
        </section>
        </div>
      </div>
    </div>
  </aside>
</template>
