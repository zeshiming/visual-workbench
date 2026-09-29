import { ref } from 'vue'

/** 图片撤回历史仅保存在内存中，关闭工作区标签页后即失效。 */
const imageUndoStacks = new Map<string, string[]>()

export const workspaceUndoRevision = ref(0)

function notifyUndoStateChanged(): void {
  workspaceUndoRevision.value += 1
}

export function recordWorkspaceImageHistory(
  workspaceId: string,
  previousImage: string | undefined,
): void {
  if (!previousImage) {
    return
  }

  const stack = imageUndoStacks.get(workspaceId) ?? []
  stack.push(previousImage)
  imageUndoStacks.set(workspaceId, stack)
  notifyUndoStateChanged()
}

export function canUndoWorkspaceImage(workspaceId: string): boolean {
  return (imageUndoStacks.get(workspaceId)?.length ?? 0) > 0
}

export function clearWorkspaceImageHistory(workspaceId: string): void {
  if (!imageUndoStacks.has(workspaceId)) {
    return
  }

  imageUndoStacks.delete(workspaceId)
  notifyUndoStateChanged()
}

export function peekWorkspaceImageUndo(workspaceId: string): string | undefined {
  const stack = imageUndoStacks.get(workspaceId)
  return stack?.[stack.length - 1]
}

export function popWorkspaceImageUndo(workspaceId: string): string | undefined {
  const stack = imageUndoStacks.get(workspaceId)
  if (!stack?.length) {
    return undefined
  }

  const previousImage = stack.pop()
  if (stack.length === 0) {
    imageUndoStacks.delete(workspaceId)
  }

  notifyUndoStateChanged()
  return previousImage
}

export function clearAllWorkspaceImageHistory(): void {
  imageUndoStacks.clear()
  notifyUndoStateChanged()
}
