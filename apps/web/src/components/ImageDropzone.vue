<script setup lang="ts">
import { ImageUp } from '@lucide/vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { pickImageFile, readImageFileAsDataUrl } from '@/lib/read-image-file'

const { t } = useI18n()

const emit = defineEmits<{
  select: [dataUrl: string]
}>()

const isDragging = ref(false)
const dragCounter = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

async function handleFiles(files: FileList | File[]): Promise<void> {
  const file = pickImageFile(files)
  if (!file) {
    return
  }

  const dataUrl = await readImageFileAsDataUrl(file)
  emit('select', dataUrl)
}

function onDragEnter(event: DragEvent): void {
  event.preventDefault()
  dragCounter.value += 1
  isDragging.value = true
}

function onDragLeave(event: DragEvent): void {
  event.preventDefault()
  dragCounter.value = Math.max(0, dragCounter.value - 1)

  if (dragCounter.value === 0) {
    isDragging.value = false
  }
}

function onDragOver(event: DragEvent): void {
  event.preventDefault()
}

async function onDrop(event: DragEvent): Promise<void> {
  event.preventDefault()
  dragCounter.value = 0
  isDragging.value = false

  if (event.dataTransfer?.files.length) {
    await handleFiles(event.dataTransfer.files)
  }
}

function openFilePicker(): void {
  inputRef.value?.click()
}

async function onInputChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) {
    return
  }

  await handleFiles(input.files)
  input.value = ''
}
</script>

<template>
  <div
    role="button"
    tabindex="0"
    class="flex w-full max-w-md cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-10 py-14 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-app-accent"
    :class="
      isDragging
        ? 'border-app-primary bg-app-accent'
        : 'border-app-border bg-app hover:border-app-muted hover:bg-app-accent'
    "
    @click="openFilePicker"
    @keydown.enter.prevent="openFilePicker"
    @keydown.space.prevent="openFilePicker"
    @dragenter="onDragEnter"
    @dragleave="onDragLeave"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <input
      ref="inputRef"
      type="file"
      accept="image/*"
      class="hidden"
      @change="onInputChange"
    />

    <div class="rounded-full bg-app-accent p-3">
      <ImageUp :size="28" :stroke-width="1.5" class="text-app-muted" />
    </div>

    <div class="text-center">
      <p class="text-sm font-medium text-app-foreground">{{ t('dropzone.dragHere') }}</p>
      <p class="mt-1 text-xs text-app-muted">{{ t('dropzone.orClick') }}</p>
    </div>
  </div>
</template>
