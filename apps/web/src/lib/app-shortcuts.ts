export type AppShortcutActions = {
  save: () => void
  undo: () => void
  exportImage: () => void
  toggleSidebar: () => void
  toggleRightSidebar: () => void
}

type ShortcutEvent = Pick<KeyboardEvent, 'metaKey' | 'ctrlKey' | 'shiftKey' | 'altKey' | 'key'>

export function handleAppShortcut(event: ShortcutEvent, actions: AppShortcutActions): boolean {
  if (!(event.metaKey || event.ctrlKey)) {
    return false
  }

  const key = event.key.toLowerCase()

  if (key === 'e' && event.shiftKey && !event.altKey) {
    actions.exportImage()
    return true
  }

  if (key === 's' && !event.shiftKey && !event.altKey) {
    actions.save()
    return true
  }

  if (key === 'z' && !event.shiftKey && !event.altKey) {
    actions.undo()
    return true
  }

  if (key === 'b' && !event.shiftKey && !event.altKey) {
    actions.toggleSidebar()
    return true
  }

  if (key === 'b' && event.shiftKey && !event.altKey) {
    actions.toggleRightSidebar()
    return true
  }

  return false
}
