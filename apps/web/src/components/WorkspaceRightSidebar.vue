<script setup lang="ts">
import { Download, LoaderCircle, Sparkles, Trash2, Wand2 } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
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
  getWorkspace,
  getWorkspaceImageRevision,
  openWorkspaces,
  setWorkspaceEditing,
  applyWorkspaceGeneratedImage,
} from '@/lib/workspace-session'
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
} from '@/lib/workspace-ui-state'
import type { EditorMark } from '@/types/editor-mark'

const props = defineProps<{
  activeWorkspaceId: string
}>()

const { t } = useI18n()

const isExporting = ref(false)
const exportError = ref('')

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
    class="flex w-64 shrink-0 flex-col border-l border-app-border bg-app"
    :aria-label="t('editorPanel.title')"
  >
    <div class="border-b border-app-border px-3 py-2.5">
      <div class="flex items-center justify-between gap-2">
        <h2 class="text-xs font-medium tracking-wide text-app-muted uppercase">
          {{ t('editorPanel.title') }}
        </h2>
        <div
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

      <div v-else-if="editMode === 'editor'" class="flex flex-col gap-3">
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

      <div v-else class="flex min-h-0 flex-1 flex-col gap-3">
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
  </aside>
</template>
