<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  assetImageUrl, deleteWorkspaceAsset, listWorkspaceAssets, uploadWorkspaceAsset,
  type ApiAsset,
} from '@/lib/api-client'
import { readImageFileAsDataUrl } from '@/lib/read-image-file'

const props = defineProps<{
  workspaceId: string
  currentImage: string | null
  beforeWrite: () => Promise<void>
}>()
const emit = defineEmits<{ select: [dataUrl: string] }>()
const assets = ref<ApiAsset[]>([])
const busy = ref(false)
const error = ref('')
const picker = ref<HTMLInputElement | null>(null)

async function refresh(): Promise<void> {
  try {
    assets.value = await listWorkspaceAssets(props.workspaceId)
    error.value = ''
  } catch {
    // A new project may exist only as an unsaved draft.
    assets.value = []
  }
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
    ))
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取图片失败'
  }
}

async function removeAsset(asset: ApiAsset): Promise<void> {
  try {
    await deleteWorkspaceAsset(props.workspaceId, asset.id)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

onMounted(() => { void refresh() })
watch(() => props.workspaceId, () => { void refresh() })
</script>

<template>
  <section class="border-t border-app-border bg-app-surface px-4 py-3" aria-label="项目素材库">
    <div class="flex items-center justify-between gap-3">
      <h2 class="text-sm font-medium text-app-foreground">项目素材库 <span class="text-app-muted">{{ assets.length }}</span></h2>
      <div class="flex gap-2">
        <input ref="picker" class="hidden" type="file" accept="image/jpeg,image/png,image/webp" multiple @change="onPick" />
        <button type="button" :disabled="busy" class="text-xs text-app-muted hover:text-app-foreground disabled:opacity-50" @click="picker?.click()">导入多张</button>
        <button type="button" :disabled="busy || !currentImage" class="text-xs text-app-muted hover:text-app-foreground disabled:opacity-50" @click="keepCurrentImage">保存当前图</button>
      </div>
    </div>
    <p v-if="error" class="mt-2 text-xs text-red-500" role="alert">{{ error }}</p>
    <p v-if="busy" class="mt-2 text-xs text-app-muted">正在处理图片…</p>
    <div v-if="assets.length" class="mt-3 flex gap-2 overflow-x-auto pb-1">
      <div v-for="asset in assets" :key="asset.id" class="group relative shrink-0">
        <button type="button" :title="`编辑 ${asset.filename}`" class="block overflow-hidden rounded border border-app-border hover:border-app-primary" @click="selectAsset(asset)">
          <img :src="assetImageUrl(workspaceId, asset.id)" :alt="asset.filename" class="h-20 w-20 object-cover" />
        </button>
        <button type="button" :aria-label="`移除 ${asset.filename}`" class="absolute right-0 top-0 bg-app-surface px-1 text-xs text-app-muted hover:text-red-500" @click="removeAsset(asset)">×</button>
      </div>
    </div>
    <p v-else-if="!busy" class="mt-2 text-xs text-app-muted">导入照片，或把修好的图片保存到这里。</p>
  </section>
</template>
