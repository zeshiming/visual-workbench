<script setup lang="ts">
import { Bot, Download, LoaderCircle, Send, Sparkles, Trash2, Wand2 } from '@lucide/vue'
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
import { previewWorkspaceAgentPlan, runWorkspaceAgent } from '@/lib/run-workspace-agent'
import { runWorkspaceAssistant } from '@/lib/run-workspace-assistant'
import { runWorkspaceEditor } from '@/lib/run-workspace-editor'
import {
  runBatchToolViaBackend,
  getWorkspaceVersionImage,
  listWorkspaceVersions,
  type ApiWorkspaceVersion,
  createAssistantSession,
  deleteAssistantSession,
  getAssistantSession,
  type ApiAssistantMessage,
  type ApiBatchJobControls,
  type ApiAgentRunControls,
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
  stageWorkspaceChanges,
  setWorkspaceEditing,
  applyWorkspaceGeneratedImage,
} from '@/lib/workspace-session'
import { loadWorkspaceImage } from '@/lib/workspace-image-storage'
import {
  clearWorkspaceRunPresentation,
  getWorkspaceAgentPrompt,
  getWorkspaceAnalysis,
  getWorkspaceAgentPlan,
  getWorkspaceToolTrace,
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
  setWorkspaceAgentPlan,
  setWorkspaceToolTrace,
  setWorkspaceEditMode,
  setWorkspaceEditorMarks,
  setWorkspaceRunError,
  setWorkspaceRunStep,
  setWorkspaceSelectedAnalysisModelId,
  setWorkspaceSelectedEditModelId,
  workspaceUiRevision,
  clearWorkspaceEditorMarks,
  addWorkspaceAssistantMessage,
  clearWorkspaceAssistantMessages,
  getWorkspaceAssistantMessages,
  getWorkspaceAssistantSessionId,
  setWorkspaceAssistantMessages,
  setWorkspaceAssistantSessionId,
  getWorkspaceSelectedAssetIds,
  getWorkspaceActiveAssetId,
  getWorkspaceAssetAdjustments,
  notifyWorkspaceAssetsChanged,
  setWorkspaceAssetAdjustments,
} from '@/lib/workspace-ui-state'
import type { AssistantMessage } from '@/lib/workspace-ui-state'
import type { EditMode } from '@/lib/edit-mode'
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
const batchControls = shallowRef<ApiBatchJobControls | null>(null)
const batchPaused = ref(false)
const batchHasFailures = ref(false)
const referencePicker = ref<HTMLInputElement | null>(null)
const referenceName = ref('')
const referenceSource = shallowRef<HTMLImageElement | null>(null)
const lutPicker = ref<HTMLInputElement | null>(null)
const lutName = ref('')
const activeStylePresetId = ref<StylePresetId | null>(null)
const expandedToolStepId = ref<string | null>(null)
const planPreviewBusy = ref(false)
const agentControls = shallowRef<ApiAgentRunControls | null>(null)
const agentPaused = ref(false)
const agentOrigin = ref<'direct' | 'assistant_handoff'>('direct')
const assistantBusy = ref(false)
const assistantInput = ref('')
const assistantError = ref('')
const versions = ref<ApiWorkspaceVersion[]>([])
const versionsBusy = ref(false)
const versionsError = ref('')
const restoringVersionId = ref<string | null>(null)
const versionThumbnails = reactive<Record<string, string>>({})
const compareVersionId = ref<string | null>(null)
const compareImage = ref<string | null>(null)
const compareDiffImage = ref<string | null>(null)
const compareBusy = ref(false)

const visibleVersions = computed(() => {
  workspaceUiRevision.value
  const assetId = activeAssetId.value
  if (!assetId) return versions.value
  return versions.value.filter((version) => !version.assetId || version.assetId === assetId)
})
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
  { value: 'agent' as const, label: 'Agent 执行' },
  { value: 'assistant' as const, label: 'AI 助理' },
  { value: 'editor' as const, label: '局部编辑' },
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

const assistantMessages = computed<AssistantMessage[]>(() => {
  workspaceUiRevision.value
  return props.activeWorkspaceId ? getWorkspaceAssistantMessages(props.activeWorkspaceId) : []
})

async function hydrateAssistantSession(): Promise<void> {
  const workspaceId = props.activeWorkspaceId
  const sessionId = workspaceId ? getWorkspaceAssistantSessionId(workspaceId) : null
  if (!workspaceId || !sessionId) return
  try {
    const session = await getAssistantSession(sessionId)
    setWorkspaceAssistantMessages(workspaceId, session.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      intent: message.intent as AssistantMessage['intent'],
      action: message.action as AssistantMessage['action'],
      suggestedPrompt: message.suggested_prompt || undefined,
      createdAt: message.created_at,
    })))
  } catch {
    // Local history remains available when the backend is offline.
  }
}

watch(() => props.activeWorkspaceId, () => { void hydrateAssistantSession() }, { immediate: true })

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

  adjustmentImage.value = image ?? null
  adjustmentBaseImage.value = image ?? null
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

async function loadWorkspaceVersions(workspaceId: string): Promise<void> {
  versionsBusy.value = true
  versionsError.value = ''
  try {
    const loadedVersions = await listWorkspaceVersions(workspaceId)
    versions.value = loadedVersions
    for (const key of Object.keys(versionThumbnails)) delete versionThumbnails[key]
    await Promise.all(loadedVersions.slice(0, 24).map(async (version) => {
      try {
        const image = await getWorkspaceVersionImage(workspaceId, version.id)
        if (image) versionThumbnails[version.id] = image
      } catch {
        // A missing thumbnail must not make the version itself unavailable.
      }
    }))
  } catch (err) {
    versions.value = []
    versionsError.value = err instanceof Error ? err.message : '版本历史加载失败'
  } finally {
    versionsBusy.value = false
  }
}

async function restoreWorkspaceVersion(version: ApiWorkspaceVersion): Promise<void> {
  const workspaceId = props.activeWorkspaceId
  const current = workspaceId ? getWorkspace(workspaceId) : null
  if (!workspaceId || !current || version.isCurrent || restoringVersionId.value) return
  restoringVersionId.value = version.id
  try {
    const image = await getWorkspaceVersionImage(workspaceId, version.id)
    if (!image) throw new Error('该版本图片不可用')
    if (current.sourceImage) recordWorkspaceImageHistory(workspaceId, current.sourceImage)
    stageWorkspaceImageChange({
      ...current,
      sourceImage: image,
      draftParentVersionId: version.id,
      hasSourceImage: true,
      updatedAt: Date.now(),
    })
  } catch (err) {
    versionsError.value = err instanceof Error ? err.message : '恢复版本失败'
  } finally {
    restoringVersionId.value = null
  }
}

async function compareWorkspaceVersion(version: ApiWorkspaceVersion): Promise<void> {
  if (!props.activeWorkspaceId || compareBusy.value) return
  compareBusy.value = true
  versionsError.value = ''
  try {
    const image = await getWorkspaceVersionImage(props.activeWorkspaceId, version.id)
    if (!image) throw new Error('该版本图片不可用')
    compareVersionId.value = version.id
    compareImage.value = image
    compareDiffImage.value = await createVersionDiff(image, workspace.value?.sourceImage ?? '')
  } catch (err) {
    versionsError.value = err instanceof Error ? err.message : '版本对比失败'
  } finally {
    compareBusy.value = false
  }
}

function closeVersionCompare(): void {
  compareVersionId.value = null
  compareImage.value = null
  compareDiffImage.value = null
}

function loadCompareImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('图片无法读取'))
    image.src = source
  })
}

async function createVersionDiff(historyImage: string, currentImage: string): Promise<string | null> {
  if (!historyImage || !currentImage) return null
  try {
    const [history, current] = await Promise.all([loadCompareImage(historyImage), loadCompareImage(currentImage)])
    const size = 320
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d')
    if (!context) return null
    context.drawImage(history, 0, 0, size, size)
    const before = context.getImageData(0, 0, size, size)
    context.clearRect(0, 0, size, size)
    context.drawImage(current, 0, 0, size, size)
    const after = context.getImageData(0, 0, size, size)
    for (let index = 0; index < before.data.length; index += 4) {
      const difference = Math.min(
        255,
        Math.abs((before.data[index] ?? 0) - (after.data[index] ?? 0))
        + Math.abs((before.data[index + 1] ?? 0) - (after.data[index + 1] ?? 0))
        + Math.abs((before.data[index + 2] ?? 0) - (after.data[index + 2] ?? 0)),
      )
      after.data[index] = difference
      after.data[index + 1] = Math.max(0, 255 - difference * 2)
      after.data[index + 2] = 0
      after.data[index + 3] = 255
    }
    context.putImageData(after, 0, 0)
    return canvas.toDataURL('image/png')
  } catch {
    return null
  }
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
  activeStylePresetId.value = presetId
  Object.assign(adjustments, preset.adjustments)
  handleAdjustmentCommit()
}

const activeStylePresetLabel = computed(() =>
  STYLE_PRESETS.find((item) => item.id === activeStylePresetId.value)?.label ?? '未选择',
)

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
  if (mode === 'reference' && !referenceSource.value) {
    batchError.value = '请先导入参考图'
    return
  }

  batchBusy.value = true
  batchError.value = ''
  batchProgress.value = 0
  batchHasFailures.value = false

  try {
    const selectedIds = getWorkspaceSelectedAssetIds(workspaceId)
    const failures: string[] = []
    await runBatchToolViaBackend(
      workspaceId,
      {
        assetIds: selectedIds,
        operation: mode === 'whiteBalance'
          ? 'white_balance'
          : mode === 'reference' ? 'reference_color' : 'adjustments',
        adjustments: { ...adjustments },
        referenceImage: mode === 'reference' ? referenceSource.value?.src : undefined,
      },
      (event) => {
        if (event.type === 'start') batchTotal.value = event.total ?? selectedIds.length
        if (event.type === 'progress') batchProgress.value = event.processed ?? batchProgress.value
        if (event.type === 'error' && event.sourceId) {
          batchHasFailures.value = true
          failures.push(event.filename ?? event.sourceId)
          batchProgress.value = event.processed ?? batchProgress.value
        }
      },
      (controls) => {
        batchControls.value = controls
        batchPaused.value = false
      },
    )

    if (failures.length) {
      batchError.value = `${failures.length} 张照片处理失败：${failures.slice(0, 2).join('、')}`
    }
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '批量调色失败'
  } finally {
    if (!batchHasFailures.value) batchControls.value = null
    batchPaused.value = false
    batchBusy.value = false
  }
}

function handleBatchStylePreset(): void {
  const workspaceId = props.activeWorkspaceId
  const styleId = activeStylePresetId.value
  if (!workspaceId || !styleId || batchBusy.value || selectedAssetCount.value === 0) return

  batchBusy.value = true
  batchError.value = ''
  batchProgress.value = 0
  batchHasFailures.value = false
  const selectedIds = getWorkspaceSelectedAssetIds(workspaceId)
  const failures: string[] = []

  void runBatchToolViaBackend(
    workspaceId,
    { assetIds: selectedIds, operation: 'style', styleId },
    (event) => {
      if (event.type === 'start') batchTotal.value = event.total ?? selectedIds.length
      if (event.type === 'progress') batchProgress.value = event.processed ?? batchProgress.value
      if (event.type === 'error' && event.sourceId) {
        batchHasFailures.value = true
        failures.push(event.filename ?? event.sourceId)
        batchProgress.value = event.processed ?? batchProgress.value
      }
    },
    (controls) => {
      batchControls.value = controls
      batchPaused.value = false
    },
  ).then(() => {
    if (failures.length) {
      batchError.value = `${failures.length} 张照片处理失败：${failures.slice(0, 2).join('、')}`
    }
    notifyWorkspaceAssetsChanged()
  }).catch((err) => {
    batchError.value = err instanceof Error ? err.message : '批量风格化失败'
  }).finally(() => {
    if (!batchHasFailures.value) batchControls.value = null
    batchPaused.value = false
    batchBusy.value = false
  })
}

async function toggleBatchPause(): Promise<void> {
  if (!batchControls.value) return
  try {
    if (batchPaused.value) {
      await batchControls.value.resume()
      batchPaused.value = false
    } else {
      await batchControls.value.pause()
      batchPaused.value = true
    }
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '批量任务操作失败'
  }
}

async function cancelBatch(): Promise<void> {
  if (!batchControls.value) return
  try {
    await batchControls.value.cancel()
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '取消批量任务失败'
  }
}

async function retryFailedBatch(): Promise<void> {
  if (!batchControls.value || batchBusy.value || !batchHasFailures.value) return
  batchBusy.value = true
  batchError.value = ''
  batchProgress.value = 0
  batchHasFailures.value = false
  try {
    await batchControls.value.retry()
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    batchError.value = err instanceof Error ? err.message : '重试批量任务失败'
  } finally {
    if (!batchHasFailures.value) batchControls.value = null
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
  ([workspaceId]) => {
    if (workspaceId) {
      void loadAdjustmentImage(workspaceId)
      return
    }

    adjustmentImage.value = null
    adjustmentBaseImage.value = null
  },
  { immediate: true },
)

watch(() => [props.activeWorkspaceId, workspace.value?.currentVersionId] as const, ([workspaceId]) => {
  if (workspaceId) void loadWorkspaceVersions(workspaceId)
  else versions.value = []
}, { immediate: true })

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

const agentPlan = computed(() => {
  workspaceUiRevision.value
  return props.activeWorkspaceId ? getWorkspaceAgentPlan(props.activeWorkspaceId) : null
})

const toolTrace = computed(() => {
  workspaceUiRevision.value
  return props.activeWorkspaceId ? getWorkspaceToolTrace(props.activeWorkspaceId) : null
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

function setEditMode(mode: EditMode) {
  if (!props.activeWorkspaceId || isWorkspaceRunning(props.activeWorkspaceId)) {
    return
  }

  setWorkspaceEditMode(props.activeWorkspaceId, mode)
  agentOrigin.value = 'direct'
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
  const approvedPlan = getWorkspaceAgentPlan(workspaceId)
  if (!approvedPlan || planPreviewBusy.value) return

  setWorkspaceRunStep(workspaceId, 'analysis')
  setWorkspaceRunError(workspaceId, '')
  setWorkspaceAnalysis(workspaceId, null)
  setWorkspaceAgentPlan(workspaceId, null)
  setWorkspaceToolTrace(workspaceId, null)
  expandedToolStepId.value = null
  setWorkspaceEditing(workspaceId, true)

  try {
    const result = await runWorkspaceAgent(currentWorkspace, prompt, {
      onProgress: (step) => {
        setWorkspaceRunStep(workspaceId, step)
      },
      modelSelection: getWorkspaceModelSelection(workspaceId),
      origin: agentOrigin.value,
      plan: approvedPlan,
      onRun: (controls) => {
        agentControls.value = controls
        agentPaused.value = false
      },
    })
    setWorkspaceAnalysis(workspaceId, result.analysis)
    setWorkspaceAgentPlan(workspaceId, result.plan ?? null)
    setWorkspaceToolTrace(workspaceId, result.toolTrace ?? null)

    const nextImage = result.images[0]
    if (!nextImage) {
      throw new Error(t('errors.editModelNoImage'))
    }

    await applyWorkspaceGeneratedImage(currentWorkspace, nextImage)
  } catch (err) {
    setWorkspaceRunError(workspaceId, err instanceof Error ? err.message : t('errors.agentFailed'))
  } finally {
    agentControls.value = null
    agentPaused.value = false
    setWorkspaceEditing(workspaceId, false)
    setWorkspaceRunStep(workspaceId, null)
    agentOrigin.value = 'direct'
  }
}

async function toggleAgentPause(): Promise<void> {
  if (!agentControls.value) return
  try {
    if (agentPaused.value) {
      await agentControls.value.resume()
      agentPaused.value = false
    } else {
      await agentControls.value.pause()
      agentPaused.value = true
    }
  } catch (err) {
    if (props.activeWorkspaceId) {
      setWorkspaceRunError(props.activeWorkspaceId, err instanceof Error ? err.message : 'Agent 任务操作失败')
    }
  }
}

async function cancelAgent(): Promise<void> {
  if (!agentControls.value) return
  try {
    await agentControls.value.cancel()
  } catch (err) {
    if (props.activeWorkspaceId) {
      setWorkspaceRunError(props.activeWorkspaceId, err instanceof Error ? err.message : '取消 Agent 任务失败')
    }
  }
}

async function handleAgentPlanPreview(): Promise<void> {
  const currentWorkspace = workspace.value
  const workspaceId = currentWorkspace?.id
  if (!currentWorkspace || !workspaceId || isWorkspaceRunning(workspaceId) || planPreviewBusy.value) return

  planPreviewBusy.value = true
  const previewPrompt = getWorkspaceAgentPrompt(workspaceId)
  const previewImage = currentWorkspace.sourceImage
  const previewRevision = getWorkspaceImageRevision(workspaceId)
  const previewSelection = getWorkspaceModelSelection(workspaceId)
  const previewSettings = JSON.stringify(loadAppSettings())
  setWorkspaceAgentPlan(workspaceId, null)
  setWorkspaceRunError(workspaceId, '')
  try {
    const result = await previewWorkspaceAgentPlan(
      currentWorkspace,
      previewPrompt,
      { modelSelection: previewSelection },
    )
    // A late preview must not authorize a different image, prompt or model.
    if (
      getWorkspaceAgentPrompt(workspaceId) !== previewPrompt
      || getWorkspace(workspaceId)?.sourceImage !== previewImage
      || getWorkspaceImageRevision(workspaceId) !== previewRevision
      || JSON.stringify(getWorkspaceModelSelection(workspaceId)) !== JSON.stringify(previewSelection)
      || JSON.stringify(loadAppSettings()) !== previewSettings
    ) {
      setWorkspaceRunError(workspaceId, '输入已变化，请重新预览执行计划。')
      return
    }
    setWorkspaceAnalysis(workspaceId, result.analysis)
    setWorkspaceAgentPlan(workspaceId, result.plan ?? null)
    setWorkspaceToolTrace(workspaceId, result.toolTrace ?? null)
  } catch (err) {
    setWorkspaceRunError(workspaceId, err instanceof Error ? err.message : '生成执行计划失败')
  } finally {
    planPreviewBusy.value = false
  }
}

async function handleAssistantSend(): Promise<void> {
  const currentWorkspace = workspace.value
  const workspaceId = currentWorkspace?.id
  const message = assistantInput.value.trim()
  if (!currentWorkspace || !workspaceId || !message || assistantBusy.value || isWorkspaceRunning(workspaceId)) {
    return
  }

  const history: ApiAssistantMessage[] = getWorkspaceAssistantMessages(workspaceId).map((item) => ({
    role: item.role,
    content: item.content,
  }))
  addWorkspaceAssistantMessage(workspaceId, {
    id: crypto.randomUUID(),
    role: 'user',
    content: message,
    createdAt: Date.now(),
  })
  assistantInput.value = ''
  assistantBusy.value = true
  assistantError.value = ''

  try {
    let sessionId = getWorkspaceAssistantSessionId(workspaceId)
    if (!sessionId) {
      const session = await createAssistantSession(workspaceId, currentWorkspace.currentVersionId ?? `image-${getWorkspaceImageRevision(workspaceId)}`)
      sessionId = session.sessionId
      setWorkspaceAssistantSessionId(workspaceId, sessionId)
    }
    const result = await runWorkspaceAssistant(
      currentWorkspace,
      message,
      history,
      {
        modelSelection: getWorkspaceModelSelection(workspaceId),
        currentVersion: currentWorkspace.currentVersionId ?? `image-${getWorkspaceImageRevision(workspaceId)}`,
        sessionId,
      },
    )
    addWorkspaceAssistantMessage(workspaceId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: result.reply,
      intent: result.intent,
      action: result.action,
      suggestedPrompt: result.suggested_prompt || undefined,
      createdAt: Date.now(),
    })
  } catch (err) {
    assistantError.value = err instanceof Error ? err.message : 'AI 助理请求失败'
  } finally {
    assistantBusy.value = false
  }
}

function useAssistantEditSuggestion(message: AssistantMessage): void {
  const workspaceId = props.activeWorkspaceId
  if (!workspaceId || !message.suggestedPrompt) return
  setWorkspaceAgentPrompt(workspaceId, message.suggestedPrompt)
  setWorkspaceEditMode(workspaceId, 'agent')
  agentOrigin.value = 'assistant_handoff'
}

async function clearAssistantHistory(): Promise<void> {
  if (props.activeWorkspaceId) {
    const sessionId = getWorkspaceAssistantSessionId(props.activeWorkspaceId)
    if (sessionId) await deleteAssistantSession(sessionId).catch(() => {})
    clearWorkspaceAssistantMessages(props.activeWorkspaceId)
    setWorkspaceAssistantSessionId(props.activeWorkspaceId, null)
  }
  assistantError.value = ''
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
    const editorResult = await runWorkspaceEditor(
      currentWorkspace,
      marks,
      getWorkspaceModelSelection(workspaceId),
      activeAssetId.value,
    )
    const nextWorkspace = await applyWorkspaceGeneratedImage(currentWorkspace, editorResult.image)
    if (editorResult.runId) {
      stageWorkspaceChanges({ ...nextWorkspace, pendingEditorRunId: editorResult.runId, pendingAssetId: activeAssetId.value })
    }
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

function toggleToolStep(stepId: string): void {
  expandedToolStepId.value = expandedToolStepId.value === stepId ? null : stepId
}

function getToolLabel(tool: string): string {
  const labels: Record<string, string> = {
    apply_ai_edit: 'AI 修图',
    apply_adjustments: '基础调色',
    apply_style: '风格化 / LUT',
    match_reference_color: '参考图追色',
    validate_result: '结果校验',
  }
  return labels[tool] ?? tool
}

function getExecutionLabel(execution: string): string {
  return { ai: 'AI', local: '本地', hybrid: '混合' }[execution] ?? execution
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
        <section v-if="batchControls && (batchBusy || batchHasFailures)" class="app-card space-y-2 p-3">
          <div class="flex items-center justify-between gap-2 text-xs">
            <span class="text-app-muted">批量任务 {{ batchProgress }}/{{ batchTotal }}</span>
            <span class="text-app-primary">{{ batchHasFailures ? '有失败素材' : batchPaused ? '已暂停' : '处理中' }}</span>
          </div>
          <div class="flex gap-2">
            <button v-if="batchBusy" type="button" class="app-btn-secondary flex-1" @click="toggleBatchPause">
              {{ batchPaused ? '继续' : '暂停' }}
            </button>
            <button v-if="batchBusy" type="button" class="app-btn-quiet flex-1 text-red-400" @click="cancelBatch">取消</button>
            <button v-if="batchHasFailures" type="button" class="app-btn-secondary flex-1" @click="retryFailedBatch">重试失败</button>
          </div>
        </section>

        <section v-if="hasImage && visibleVersions.length" class="app-card space-y-2 p-3">
          <div class="flex items-center justify-between gap-2">
            <div>
              <div class="app-eyebrow">IMAGE VERSIONS</div>
              <h3 class="mt-1 text-sm font-medium text-app-foreground">版本历史</h3>
            </div>
            <button type="button" class="app-btn-quiet" :disabled="versionsBusy" @click="loadWorkspaceVersions(activeWorkspaceId)">刷新</button>
          </div>
          <div class="max-h-36 space-y-1 overflow-y-auto">
            <div v-for="version in visibleVersions" :key="version.id" class="flex items-center justify-between gap-2 rounded border border-app-border px-2 py-1.5 text-xs">
              <div class="flex min-w-0 items-center gap-2">
                <img v-if="versionThumbnails[version.id]" :src="versionThumbnails[version.id]" alt="" class="h-9 w-9 shrink-0 rounded object-cover" />
                <p class="truncate text-app-foreground">{{ version.operation }} · {{ version.id.slice(0, 8) }}</p>
                <p class="text-[10px] text-app-subtle">
                  {{ version.isCurrent ? '当前版本' : '历史版本' }}
                  <span v-if="version.parentId"> · 父 {{ version.parentId.slice(0, 8) }}</span>
                </p>
              </div>
              <button v-if="!version.isCurrent" type="button" class="app-btn-quiet shrink-0" :disabled="!!restoringVersionId" @click="restoreWorkspaceVersion(version)">
                {{ restoringVersionId === version.id ? '读取中…' : '恢复为草稿' }}
              </button>
              <button type="button" class="app-btn-quiet shrink-0" :disabled="compareBusy" @click="compareWorkspaceVersion(version)">
                {{ compareVersionId === version.id && compareBusy ? '读取中…' : '对比' }}
              </button>
            </div>
          </div>
          <div v-if="compareImage && workspace?.sourceImage" class="space-y-2 rounded border border-app-border p-2">
            <div class="flex items-center justify-between gap-2">
              <p class="text-[10px] text-app-subtle">历史版本 / 当前草稿</p>
              <button type="button" class="app-btn-quiet" @click="closeVersionCompare">关闭</button>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <img :src="compareImage" alt="历史版本" class="aspect-square w-full rounded object-cover" />
              <img :src="workspace.sourceImage" alt="当前草稿" class="aspect-square w-full rounded object-cover" />
              <img v-if="compareDiffImage" :src="compareDiffImage" alt="差异热图" class="aspect-square w-full rounded object-cover" />
            </div>
          </div>
          <p v-if="versionsError" class="text-[10px] text-red-400">{{ versionsError }}</p>
          <p class="text-[10px] leading-relaxed text-app-subtle">{{ activeAssetId ? '已按当前素材筛选；' : '' }}恢复只生成当前工作区草稿，保存后才创建新的版本。</p>
        </section>

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
          <div v-if="selectedAssetCount" class="border-t border-app-border pt-3">
            <p class="mb-2 text-[11px] text-app-subtle">当前预设：{{ activeStylePresetLabel }}</p>
            <button type="button" class="app-btn-primary w-full" :disabled="adjustmentBusy || batchBusy || isRunning || !activeStylePresetId" @click="handleBatchStylePreset">
              <LoaderCircle v-if="batchBusy" :size="14" :stroke-width="1.8" class="animate-spin" />
              <Wand2 v-else :size="14" :stroke-width="1.8" />
              {{ batchBusy ? `正在处理 ${batchProgress}/${batchTotal}` : `应用到已选 ${selectedAssetCount} 张` }}
            </button>
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
              @click="() => handleBatchAdjustments()"
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

        <div v-else-if="workspaceMode === 'ai' && editMode === 'assistant'" class="flex min-h-0 flex-1 flex-col gap-3">
        <div class="app-card space-y-2 p-3">
          <div class="flex items-center gap-2">
            <Bot :size="16" :stroke-width="1.8" class="text-app-primary" />
            <h3 class="text-sm font-medium text-app-foreground">AI 助理</h3>
          </div>
          <p class="text-[11px] leading-relaxed text-app-subtle">
            这里负责分析、解释和安排工作，不会在对话时直接调用修图模型。需要修改图片时，会交给 Agent 先预览计划。
          </p>
        </div>

        <div class="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          <div v-if="assistantMessages.length === 0" class="app-card border-dashed px-3 py-6 text-center text-xs leading-relaxed text-app-subtle">
            你可以问：这张照片的问题是什么？<br />或者：应该用基础调色还是 AI 修图？
          </div>
          <div
            v-for="message in assistantMessages"
            :key="message.id"
            class="flex"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[92%] rounded-lg px-3 py-2 text-xs leading-relaxed"
              :class="message.role === 'user' ? 'bg-app-primary text-white' : 'border border-app-border bg-app-surface text-app-foreground'"
            >
              {{ message.content }}
              <button
                v-if="message.role === 'assistant' && message.action === 'preview_edit' && message.suggestedPrompt"
                type="button"
                class="mt-2 flex w-full items-center justify-center gap-1.5 rounded border border-app-border px-2 py-1.5 text-[11px] text-app-primary transition hover:bg-app-elevated"
                @click="useAssistantEditSuggestion(message)"
              >
                <Sparkles :size="12" :stroke-width="1.8" />
                交给 Agent 预览修图计划
              </button>
            </div>
          </div>
        </div>

        <div class="space-y-2 border-t border-app-border pt-3">
          <textarea
            v-model="assistantInput"
            rows="3"
            class="app-field resize-none"
            placeholder="向 AI 助理描述目标、询问问题或继续当前任务…"
            :disabled="assistantBusy || isRunning"
            @keydown.enter.exact.prevent="handleAssistantSend"
          />
          <div class="flex gap-2">
            <button
              type="button"
              class="app-btn-primary flex-1"
              :disabled="assistantBusy || isRunning || !assistantInput.trim()"
              @click="handleAssistantSend"
            >
              <LoaderCircle v-if="assistantBusy" :size="14" :stroke-width="1.8" class="animate-spin" />
              <Send v-else :size="14" :stroke-width="1.8" />
              {{ assistantBusy ? '思考中…' : '发送' }}
            </button>
            <button
              type="button"
              class="app-btn-quiet"
              :disabled="assistantBusy || assistantMessages.length === 0"
              @click="clearAssistantHistory"
            >
              清空
            </button>
          </div>
          <p v-if="assistantError" class="text-xs text-red-400">{{ assistantError }}</p>
        </div>
        </div>

        <div v-else-if="workspaceMode === 'ai' && editMode === 'agent'" class="flex min-h-0 flex-1 flex-col gap-3">
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
          class="app-btn-secondary w-full"
          :disabled="isRunning || planPreviewBusy"
          @click="handleAgentPlanPreview"
        >
          <LoaderCircle v-if="planPreviewBusy" :size="15" :stroke-width="1.75" class="animate-spin" />
          <Sparkles v-else :size="15" :stroke-width="1.75" />
          {{ planPreviewBusy ? '正在生成计划…' : agentPlan ? '重新预览执行计划' : '预览执行计划' }}
        </button>

        <button
          type="button"
          class="app-btn-primary w-full"
          :disabled="isRunning || planPreviewBusy || !agentPlan"
          @click="handleAgentRun"
        >
          <LoaderCircle v-if="isRunning" :size="15" :stroke-width="1.75" class="animate-spin" />
          <Sparkles v-else :size="15" :stroke-width="1.75" />
          {{ isRunning ? t('common.processing') : '确认计划并执行' }}
        </button>

        <section v-if="isRunning && agentControls" class="app-card space-y-2 p-3">
          <div class="flex items-center justify-between text-xs">
            <span class="text-app-muted">Agent 任务</span>
            <span class="text-app-primary">{{ agentPaused ? '已暂停' : '处理中' }}</span>
          </div>
          <div class="flex gap-2">
            <button type="button" class="app-btn-secondary flex-1" @click="toggleAgentPause">
              {{ agentPaused ? '继续' : '暂停' }}
            </button>
            <button type="button" class="app-btn-quiet flex-1 text-red-400" @click="cancelAgent">取消</button>
          </div>
          <p class="text-[10px] leading-relaxed text-app-subtle">当前模型请求完成后，任务会在下一阶段暂停。</p>
        </section>

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

        <section v-if="agentPlan" class="app-card space-y-3 p-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-xs font-medium uppercase text-app-muted">Agent 执行计划</h3>
            <span class="rounded border border-app-border px-1.5 py-0.5 text-[10px] text-app-subtle">
              {{ getExecutionLabel(agentPlan.execution) }}
            </span>
          </div>
          <p class="text-xs leading-relaxed text-app-muted">{{ agentPlan.goal }}</p>
          <ol class="space-y-1.5">
            <li
              v-for="(step, index) in agentPlan.steps"
              :key="step.id"
              class="flex gap-2 rounded border border-app-border bg-app-surface px-2 py-1.5"
            >
              <span class="text-[10px] text-app-subtle">{{ index + 1 }}</span>
              <div class="min-w-0">
                <p class="text-xs text-app-foreground">{{ getToolLabel(step.tool) }}</p>
                <p v-if="step.rationale" class="mt-0.5 text-[10px] leading-relaxed text-app-subtle">{{ step.rationale }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section v-if="toolTrace" class="app-card space-y-3 p-3">
          <h3 class="text-xs font-medium uppercase text-app-muted">工具执行轨迹</h3>
          <div
            v-for="run in toolTrace.runs"
            :key="run.stepId"
            class="rounded border border-app-border bg-app-surface"
          >
            <button
              type="button"
              class="flex w-full items-start justify-between gap-2 px-2.5 py-2 text-left text-xs"
              :aria-expanded="expandedToolStepId === run.stepId"
              @click="toggleToolStep(run.stepId)"
            >
              <div class="min-w-0">
                <p class="text-app-foreground">{{ getToolLabel(run.tool) }}</p>
                <p class="mt-0.5 text-[10px] text-app-subtle">步骤 {{ run.stepId }}</p>
              </div>
              <span
                class="shrink-0 rounded px-1.5 py-0.5 text-[10px]"
                :class="run.status === 'failed' ? 'bg-red-500/10 text-red-400' : run.status === 'deferred' ? 'bg-amber-500/10 text-amber-400' : run.status === 'skipped' ? 'bg-slate-500/10 text-slate-400' : 'bg-emerald-500/10 text-emerald-400'"
              >
                {{ run.status === 'failed' ? '失败' : run.status === 'deferred' ? '等待' : run.status === 'skipped' ? '已跳过' : '完成' }}
              </span>
            </button>
            <div v-if="expandedToolStepId === run.stepId" class="border-t border-app-border px-2.5 py-2">
              <p class="text-[10px] leading-relaxed text-app-muted">{{ run.message }}</p>
            </div>
          </div>
          <button
            v-if="toolTrace.hasFailures"
            type="button"
            class="app-btn-secondary w-full"
            :disabled="isRunning"
            @click="handleAgentRun"
          >
            重新执行 Agent
          </button>
        </section>

        <section v-if="toolTrace?.aiCalls?.length" class="app-card space-y-3 p-3">
          <h3 class="text-xs font-medium uppercase text-app-muted">模型请求 Trace</h3>
          <div v-for="call in toolTrace.aiCalls" :key="`${call.model}-${call.durationMs}`" class="rounded border border-app-border bg-app-surface px-2.5 py-2 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="text-app-foreground">{{ call.model }}</span>
              <span :class="call.status === 'completed' ? 'text-emerald-400' : 'text-red-400'">{{ call.status === 'completed' ? '完成' : '失败' }}</span>
            </div>
            <p class="mt-1 text-[10px] text-app-subtle">{{ call.protocol }} · {{ call.durationMs }}ms</p>
            <p v-if="call.error" class="mt-1 text-[10px] text-red-400">{{ call.error }}</p>
          </div>
        </section>
        </div>
      </div>
    </div>
  </aside>
</template>
