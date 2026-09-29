<script setup lang="ts">
import { Check, Download, Images, Save, Search, Trash2, Upload, X } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import {
  assetImageUrl, deleteWorkspaceAsset, exportWorkspaceAssets, listWorkspaceAssets, uploadWorkspaceAsset,
  type ApiAsset,
} from '@/lib/api-client'
import { readImageFileAsDataUrl } from '@/lib/read-image-file'
import { scoreImageForCuration } from '@/lib/image-curation'
import {
  getWorkspaceSelectedAssetIds,
  notifyWorkspaceAssetsChanged,
  setWorkspaceSelectedAssetIds,
  workspaceAssetsRevision,
} from '@/lib/workspace-ui-state'

const props = withDefaults(defineProps<{
  workspaceId: string
  currentImage: string | null
  beforeWrite: () => Promise<void>
  placement?: 'bottom' | 'sidebar'
}>(), {
  placement: 'bottom',
})
const emit = defineEmits<{ select: [dataUrl: string, assetId?: string] }>()
const assets = ref<ApiAsset[]>([])
const busy = ref(false)
const error = ref('')
const picker = ref<HTMLInputElement | null>(null)
const folderPicker = ref<HTMLInputElement | null>(null)
const searchQuery = ref('')
const libraryFilter = ref<'all' | 'paired' | 'raw' | 'jpg' | 'selected'>('all')
const selectedAssetIds = ref<Set<string>>(new Set(getWorkspaceSelectedAssetIds(props.workspaceId)))
const smartBusy = ref(false)
const smartMessage = ref('')
const idSelectionMessage = ref('')
const smartScores = ref<Map<string, number>>(new Map())

const feedbackIds = computed(() => {
  const ids = new Set<string>()
  const tokens = searchQuery.value.split(/[\s,，、;；]+/).map((token) => token.trim()).filter(Boolean)

  for (const token of tokens) {
    const range = token.match(/^(\d{2,})[-~～—](\d{2,})$/)
    if (range) {
      const start = Number(range[1])
      const end = Number(range[2])
      if (end >= start && end - start <= 500) {
        for (let value = start; value <= end; value += 1) ids.add(String(value))
      }
      continue
    }

    if (/^\d{2,}$/.test(token)) ids.add(token)
  }

  return [...ids]
})

const rawCount = computed(() => assets.value.filter((asset) => asset.pairRole === 'raw').length)
const pairedRawCount = computed(() => assets.value.filter((asset) => asset.pairRole === 'raw' && asset.pairGroup).length)
const pairProgress = computed(() => rawCount.value ? Math.round((pairedRawCount.value / rawCount.value) * 100) : 0)
const libraryCategories = computed(() => [
  { id: 'all' as const, label: '全部照片', count: assets.value.length },
  { id: 'paired' as const, label: 'JPG + RAW', count: assets.value.filter((asset) => asset.pairGroup).length },
  { id: 'raw' as const, label: '仅 RAW', count: rawCount.value },
  { id: 'jpg' as const, label: '仅 JPG', count: assets.value.filter((asset) => asset.pairRole === 'jpeg').length },
  { id: 'selected' as const, label: '已选择', count: selectedCount.value },
])

const categoryAssets = computed(() => {
  if (libraryFilter.value === 'paired') return assets.value.filter((asset) => Boolean(asset.pairGroup))
  if (libraryFilter.value === 'raw') return assets.value.filter((asset) => asset.pairRole === 'raw')
  if (libraryFilter.value === 'jpg') return assets.value.filter((asset) => asset.pairRole === 'jpeg')
  if (libraryFilter.value === 'selected') return assets.value.filter((asset) => selectedAssetIds.value.has(asset.id))
  return assets.value
})

const idMatchedAssets = computed(() => {
  if (!feedbackIds.value.length) return [] as ApiAsset[]
  return categoryAssets.value.filter((asset) =>
    feedbackIds.value.some((id) => asset.filename.toLowerCase().includes(id.toLowerCase())),
  )
})

const filteredAssets = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return categoryAssets.value
  if (feedbackIds.value.length) return idMatchedAssets.value
  return categoryAssets.value.filter((asset) => asset.filename.toLowerCase().includes(query))
})

const selectedCount = computed(() => selectedAssetIds.value.size)

function isSelected(assetId: string): boolean {
  return selectedAssetIds.value.has(assetId)
}

function toggleSelection(assetId: string): void {
  const next = new Set(selectedAssetIds.value)
  if (next.has(assetId)) {
    next.delete(assetId)
  } else {
    next.add(assetId)
  }
  selectedAssetIds.value = next
  setWorkspaceSelectedAssetIds(props.workspaceId, [...next])
}

function selectAllVisible(): void {
  selectedAssetIds.value = new Set(filteredAssets.value.map((asset) => asset.id))
  setWorkspaceSelectedAssetIds(props.workspaceId, [...selectedAssetIds.value])
}

function clearSelection(): void {
  selectedAssetIds.value = new Set()
  setWorkspaceSelectedAssetIds(props.workspaceId, [])
}

function selectFeedbackIds(): void {
  if (!idMatchedAssets.value.length) return
  selectedAssetIds.value = new Set(idMatchedAssets.value.map((asset) => asset.id))
  setWorkspaceSelectedAssetIds(props.workspaceId, [...selectedAssetIds.value])
  idSelectionMessage.value = `已按编号选中 ${idMatchedAssets.value.length} 张照片`
}

function openFirstSelected(): void {
  const asset = assets.value.find((item) => selectedAssetIds.value.has(item.id))
  if (asset) void selectAsset(asset)
}

function hashDistance(left: string, right: string): number {
  let distance = 0
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    if (left[index] !== right[index]) distance += 1
  }
  return distance + Math.abs(left.length - right.length)
}

async function exportSelected(): Promise<void> {
  if (!selectedAssetIds.value.size || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const blob = await exportWorkspaceAssets(props.workspaceId, [...selectedAssetIds.value])
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'photo-library-export.zip'
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '导出失败'
  } finally {
    busy.value = false
  }
}

async function smartCurate(): Promise<void> {
  if (!assets.value.length || smartBusy.value) return
  smartBusy.value = true
  smartMessage.value = ''
  try {
    const scored: Array<{ id: string; score: number; hash: string }> = []
    for (const asset of assets.value) {
      const response = await fetch(assetImageUrl(props.workspaceId, asset.id))
      if (!response.ok) continue
      const source = await readImageFileAsDataUrl(
        new File([await response.blob()], asset.filename, { type: asset.mediaType }),
      )
      const result = await scoreImageForCuration(source)
      scored.push({ id: asset.id, score: result.score, hash: result.hash })
    }

    scored.sort((left, right) => right.score - left.score)
    smartScores.value = new Map(scored.map((item) => [item.id, item.score]))
    const groups: Array<typeof scored> = []
    for (const item of scored) {
      const group = groups.find((candidate) => hashDistance(candidate[0]!.hash, item.hash) <= 6)
      if (group) group.push(item)
      else groups.push([item])
    }
    selectedAssetIds.value = new Set(groups.map((group) => group[0]!.id))
    setWorkspaceSelectedAssetIds(props.workspaceId, [...selectedAssetIds.value])
    const duplicateCount = groups.filter((group) => group.length > 1).length
    smartMessage.value = `已选出 ${selectedAssetIds.value.size} 张，识别到 ${duplicateCount} 组相似照片`
  } catch (err) {
    error.value = err instanceof Error ? err.message : '智能选片失败'
  } finally {
    smartBusy.value = false
  }
}

async function refresh(): Promise<void> {
  try {
    assets.value = await listWorkspaceAssets(props.workspaceId)
    error.value = ''
  } catch {
    // A new project may exist only as an unsaved draft.
    assets.value = []
  }

  const existingIds = new Set(assets.value.map((asset) => asset.id))
  selectedAssetIds.value = new Set(
    [...selectedAssetIds.value].filter((assetId) => existingIds.has(assetId)),
  )
  setWorkspaceSelectedAssetIds(props.workspaceId, [...selectedAssetIds.value])
}

async function upload(files: File[]): Promise<void> {
  if (!files.length) return
  busy.value = true
  error.value = ''
  try {
    await props.beforeWrite()
    for (const file of files) {
      await uploadWorkspaceAsset(props.workspaceId, file)
    }
    await refresh()
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '导入失败'
    await refresh()
  } finally {
    busy.value = false
  }
}

async function onPick(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  await upload(files)
}

async function onPickFolder(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  await upload(files)
}

async function keepCurrentImage(): Promise<void> {
  if (!props.currentImage) return
  busy.value = true
  error.value = ''
  try {
    await props.beforeWrite()
    const response = await fetch(props.currentImage)
    const blob = await response.blob()
    const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'
    const filename = `作品-${new Date().toISOString().replace(/[:.]/g, '-')}.${extension}`
    await uploadWorkspaceAsset(props.workspaceId, new File([blob], filename, { type: blob.type }), 'edit')
    await refresh()
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    busy.value = false
  }
}

async function selectAsset(asset: ApiAsset): Promise<void> {
  try {
    const response = await fetch(assetImageUrl(props.workspaceId, asset.id))
    if (!response.ok) throw new Error('读取图片失败')
    emit('select', await readImageFileAsDataUrl(
      new File([await response.blob()], asset.filename, { type: asset.mediaType }),
    ), asset.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取图片失败'
  }
}

async function removeAsset(asset: ApiAsset): Promise<void> {
  try {
    await deleteWorkspaceAsset(props.workspaceId, asset.id)
    await refresh()
    notifyWorkspaceAssetsChanged()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

onMounted(() => { void refresh() })
watch(() => props.workspaceId, () => {
  selectedAssetIds.value = new Set(getWorkspaceSelectedAssetIds(props.workspaceId))
  void refresh()
})
watch(workspaceAssetsRevision, () => { void refresh() })
</script>

<template>
  <section class="app-contact-sheet border-t border-app-border bg-app-surface px-4 py-3" :class="{ 'app-asset-sidebar': placement === 'sidebar' }" aria-label="项目照片库">
    <div class="flex items-start justify-between gap-3">
      <div class="flex min-w-0 items-center gap-2.5">
        <div class="app-filmstrip-icon"><Images :size="14" :stroke-width="1.8" /></div>
        <div class="min-w-0">
          <div class="app-eyebrow">PHOTO LIBRARY / CONTACT SHEET</div>
          <h2 class="mt-1 truncate text-sm font-medium tracking-tight text-app-foreground">
            照片库 <span class="text-app-muted">{{ assets.length }}</span>
          </h2>
        </div>
      </div>
      <div class="flex shrink-0 gap-1.5">
        <input ref="picker" class="hidden" type="file" accept="image/jpeg,image/png,image/webp,.arw,.cr2,.cr3,.dng,.nef,.orf,.pef,.raf,.rw2,.srw" multiple @change="onPick" />
        <input ref="folderPicker" class="hidden" type="file" webkitdirectory directory multiple @change="onPickFolder" />
        <button type="button" :disabled="busy" class="app-btn-quiet" @click="picker?.click()"><Upload :size="13" />导入照片</button>
        <button type="button" :disabled="busy" class="app-btn-quiet" @click="folderPicker?.click()"><Images :size="13" />导入文件夹</button>
        <button type="button" :disabled="busy || !currentImage" class="app-btn-quiet" @click="keepCurrentImage"><Save :size="13" />保存当前</button>
      </div>
    </div>

    <div class="app-library-categories mt-3 flex flex-wrap gap-1.5">
      <button v-for="item in libraryCategories" :key="item.id" type="button" class="app-library-category" :class="{ 'app-library-category-active': libraryFilter === item.id }" @click="libraryFilter = item.id">
        <span>{{ item.label }}</span><strong>{{ item.count }}</strong>
      </button>
    </div>
    <div v-if="rawCount" class="app-pair-progress mt-2">
      <div class="flex items-center justify-between text-[10px] text-app-subtle"><span>RAW 配对完成度</span><span>{{ pairProgress }}%</span></div>
      <div class="app-pair-progress-track"><span :style="{ width: `${pairProgress}%` }" /></div>
    </div>

    <div class="app-contact-toolbar mt-3 flex flex-wrap items-center gap-2">
      <label class="app-contact-search flex min-w-40 flex-1 items-center gap-2">
        <Search :size="14" :stroke-width="1.7" class="text-app-subtle" />
        <input v-model="searchQuery" type="search" placeholder="输入照片编号，如 3405 3407" aria-label="按照片编号或文件名搜索" />
      </label>
      <span class="app-selection-count">已选 {{ selectedCount }} 张</span>
      <button type="button" class="app-btn-quiet app-btn-quiet-accent" :disabled="!idMatchedAssets.length" @click="selectFeedbackIds">按编号选片</button>
      <button type="button" class="app-btn-quiet" :disabled="!filteredAssets.length" @click="selectAllVisible">全选当前</button>
      <button type="button" class="app-btn-quiet" :disabled="selectedCount === 0" @click="clearSelection">清空</button>
      <button type="button" class="app-btn-quiet app-btn-quiet-accent" :disabled="selectedCount === 0" @click="openFirstSelected">编辑首张</button>
      <button type="button" class="app-btn-quiet app-btn-quiet-accent" :disabled="selectedCount === 0 || busy" @click="exportSelected"><Download :size="13" />导出已选</button>
      <button type="button" class="app-btn-quiet app-btn-quiet-accent" :disabled="!assets.length || smartBusy || busy" @click="smartCurate">{{ smartBusy ? '分析中…' : '智能选片' }}</button>
    </div>

    <p v-if="error" class="mt-2 text-xs text-red-500" role="alert">{{ error }}</p>
    <p v-if="busy" class="mt-2 text-xs text-app-muted">正在处理图片…</p>
    <p v-if="smartMessage" class="mt-2 text-xs text-app-primary">{{ smartMessage }}</p>
    <p v-if="idSelectionMessage" class="mt-2 text-xs text-app-primary">{{ idSelectionMessage }}</p>

    <div v-if="filteredAssets.length" class="app-contact-grid mt-3">
      <article
        v-for="(asset, index) in filteredAssets"
        :key="asset.id"
        class="app-contact-card group"
        :title="[asset.width && asset.height ? `${asset.width} × ${asset.height}` : '', asset.metadata?.Model || asset.metadata?.camera || ''].filter(Boolean).join(' · ')"
      >
        <button type="button" :title="`打开 ${asset.filename}`" class="app-contact-thumb" @click="selectAsset(asset)">
          <img :src="assetImageUrl(workspaceId, asset.id)" :alt="asset.filename" />
          <span class="app-contact-index">{{ index + 1 }}</span>
          <span v-if="smartScores.has(asset.id)" class="app-contact-score">{{ smartScores.get(asset.id) }}</span>
          <span class="app-contact-selected" :class="{ 'app-contact-selected-active': isSelected(asset.id) }" @click.stop="toggleSelection(asset.id)">
            <Check v-if="isSelected(asset.id)" :size="12" :stroke-width="2.5" />
          </span>
        </button>
        <div class="mt-1 flex items-center justify-between gap-1">
          <p class="min-w-0 truncate text-[10px] text-app-subtle">
            {{ asset.filename }}
            <span v-if="asset.pairRole === 'raw'" class="ml-1 text-app-primary">RAW</span>
            <span v-else-if="asset.pairGroup" class="ml-1 text-app-muted">JPG+RAW</span>
          </p>
          <p v-if="asset.width || asset.metadata?.Model || asset.metadata?.camera" class="truncate text-[9px] text-app-subtle">
            {{ asset.width && asset.height ? `${asset.width} × ${asset.height}` : '' }}
            {{ asset.metadata?.Model || asset.metadata?.camera || '' }}
          </p>
          <button type="button" :aria-label="`移除 ${asset.filename}`" class="app-contact-remove opacity-0 transition group-hover:opacity-100" @click="removeAsset(asset)"><X :size="12" /></button>
        </div>
      </article>
    </div>
    <p v-else-if="!busy" class="app-contact-empty mt-3">{{ assets.length ? '没有匹配的照片。' : '导入照片，开始建立项目联系表。' }}</p>
  </section>
</template>
