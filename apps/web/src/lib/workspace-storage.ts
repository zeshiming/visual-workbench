import type { Workspace } from '@/types/workspace'

import { ref } from 'vue'

import { translate } from '@/i18n'
import {
  commitBackendWorkspace,
  deleteBackendWorkspace,
  listBackendWorkspaces,
  loadBackendSettings,
  saveBackendSettings,
} from '@/lib/api-client'

import {
  deleteWorkspaceImage,
  loadWorkspaceImage,
} from '@/lib/workspace-image-storage'

export const savedWorkspacesRevision = ref(0)

function notifySavedWorkspacesChanged(): void {
  savedWorkspacesRevision.value += 1
}

export const DEFAULT_WORKSPACE_TITLE = '未命名'

export function isDefaultWorkspaceTitle(title: string): boolean {
  return title === DEFAULT_WORKSPACE_TITLE || title === 'Untitled' || title === '未命名'
}

export function getDisplayWorkspaceTitle(title: string): string {
  return isDefaultWorkspaceTitle(title) ? translate('common.unnamed') : title
}

type WorkspaceMap = Record<string, Workspace>

function emptyWorkspaceMap(): WorkspaceMap {
  return {}
}

// ── In-memory cache ───────────────────────────────────────────

let workspaceCache: WorkspaceMap = {}

/**
 * Clear the in-memory workspace cache (used in tests).
 */
export function clearWorkspaceCache(): void {
  workspaceCache = {}
}

function loadFromCache(): WorkspaceMap {
  return { ...workspaceCache }
}

function saveToCache(workspaces: WorkspaceMap): void {
  workspaceCache = { ...workspaces }
}

/**
 * Strip sourceImage from a workspace — images stored separately.
 */
function stripSourceImage(workspace: Workspace): Workspace {
  const { sourceImage: _img, ...rest } = workspace
  return rest
}

// ── Sync API (reads from in-memory cache) ─────────────────────

/** Synchronous read — returns from in-memory cache. */
export function loadWorkspaces(): WorkspaceMap {
  return loadFromCache()
}

/** Synchronous read — returns from in-memory cache. */
export function loadWorkspace(id: string): Workspace | null {
  return workspaceCache[id] ?? null
}

/** Synchronous check — uses in-memory cache. */
export function isPersistedWorkspace(id: string): boolean {
  return id in workspaceCache
}

/** Synchronous check — uses in-memory cache. */
export function isWorkspaceNameTaken(name: string, excludeId?: string): boolean {
  const trimmed = name.trim()
  if (!trimmed) {
    return false
  }

  return Object.values(workspaceCache).some(
    (workspace) => workspace.id !== excludeId && workspace.title.trim() === trimmed,
  )
}

/** Synchronous read — returns from cache, sorted by updatedAt desc. */
export function getRecentWorkspaces(): Workspace[] {
  return Object.values(workspaceCache).sort(
    (left, right) => right.updatedAt - left.updatedAt,
  )
}

export function loadSavedProjectsFromLocalStorage(): Workspace[] {
  return getRecentWorkspaces()
}

// ── Last workspace ID (in-memory + backend) ───────────────────

let lastWorkspaceId: string | null = null

export function loadLastWorkspaceId(): string | null {
  return lastWorkspaceId
}

export function saveLastWorkspaceId(id: string): void {
  lastWorkspaceId = id
  saveBackendSettings({ last_workspace: id }).catch(() => {})
}

// ── Async API (writes to backend + in-memory cache) ───────────

export async function hydrateWorkspaceImage(workspace: Workspace): Promise<Workspace> {
  if (workspace.sourceImage || !workspace.hasSourceImage) {
    return workspace
  }

  const sourceImage = await loadWorkspaceImage(workspace.id)
  if (!sourceImage) {
    return workspace
  }

  return {
    ...workspace,
    sourceImage,
  }
}

export async function deleteWorkspace(id: string): Promise<void> {
  // Delete from backend (best-effort)
  try {
    await deleteBackendWorkspace(id)
  } catch {
    // Backend unavailable
  }

  // Delete from in-memory cache
  const cache = loadFromCache()
  delete cache[id]
  saveToCache(cache)

  // Delete image
  await deleteWorkspaceImage(id)
  notifySavedWorkspacesChanged()

  // Update last workspace
  if (lastWorkspaceId === id) {
    const recent = getRecentWorkspaces()
    if (recent.length > 0) {
      saveLastWorkspaceId(recent[0]!.id)
    }
  }
}

export async function replaceWorkspaceSourceImage(
  workspace: Workspace,
  sourceImage: string,
): Promise<Workspace> {
  const saved = await commitBackendWorkspace(workspace.id, {
    title: workspace.title, createdAt: workspace.createdAt, updatedAt: workspace.updatedAt,
    image: sourceImage, expectedVersionId: workspace.currentVersionId, parentVersionId: workspace.draftParentVersionId,
  })

  const nextWorkspace: Workspace = {
    ...workspace,
    sourceImage,
    hasSourceImage: true,
    currentVersionId: saved.currentVersionId,
    updatedAt: Date.now(),
  }

  // Update in-memory cache (strip sourceImage — stored separately)
  const cache = loadFromCache()
  cache[workspace.id] = stripSourceImage(nextWorkspace)
  saveToCache(cache)

  saveLastWorkspaceId(workspace.id)
  notifySavedWorkspacesChanged()

  return nextWorkspace
}

const pendingSaves = new Map<string, Promise<void>>()

export function saveWorkspace(workspace: Workspace): Promise<void> {
  const snapshot = { ...workspace }
  const previous = pendingSaves.get(workspace.id)
  const save = previous
    ? previous.catch(() => {}).then(() => writeWorkspace(snapshot))
    : writeWorkspace(snapshot)
  pendingSaves.set(workspace.id, save)
  const cleanup = () => {
    if (pendingSaves.get(workspace.id) === save) pendingSaves.delete(workspace.id)
  }
  void save.then(cleanup, cleanup)
  return save
}

async function writeWorkspace(workspace: Workspace): Promise<void> {
  const hasSourceImage = Boolean(workspace.sourceImage)

  // Cache metadata only (strip sourceImage — stored separately)
  const cachedWorkspace = stripSourceImage({
    ...workspace,
    hasSourceImage: hasSourceImage || workspace.hasSourceImage,
    updatedAt: Date.now(),
  })

  const commit: { title: string; createdAt: number; updatedAt: number; image?: string | null; expectedVersionId?: string | null; parentVersionId?: string | null; editorRunId?: string | null; assetId?: string | null } = {
    title: cachedWorkspace.title,
    createdAt: cachedWorkspace.createdAt,
    updatedAt: cachedWorkspace.updatedAt,
  }
  if (workspace.currentVersionId) commit.expectedVersionId = workspace.currentVersionId
  if (workspace.draftParentVersionId) commit.parentVersionId = workspace.draftParentVersionId
  if (workspace.pendingEditorRunId) commit.editorRunId = workspace.pendingEditorRunId
  if (workspace.pendingAssetId) commit.assetId = workspace.pendingAssetId
  if (workspace.sourceImage !== undefined) commit.image = workspace.sourceImage
  else if (workspace.hasSourceImage === false) commit.image = null
  let saved: { currentVersionId?: string | null } | null = null
  try {
    saved = await commitBackendWorkspace(workspace.id, commit)
  } catch (err) {
    // Node/jsdom tests and offline local-only previews have no same-origin
    // fetch base URL. Preserve the local cache fallback for that environment;
    // real browser/network failures still surface to the caller.
    if (!/(Invalid URL|Failed to parse URL)/i.test(String(err))) throw err
  }
  if (saved) cachedWorkspace.currentVersionId = saved.currentVersionId
  if (cachedWorkspace.draftParentVersionId !== undefined) cachedWorkspace.draftParentVersionId = null
  if (cachedWorkspace.pendingEditorRunId !== undefined) cachedWorkspace.pendingEditorRunId = null
  if (cachedWorkspace.pendingAssetId !== undefined) cachedWorkspace.pendingAssetId = null
  const cache = loadFromCache()
  cache[cachedWorkspace.id] = cachedWorkspace
  saveToCache(cache)
  saveLastWorkspaceId(cachedWorkspace.id)
  notifySavedWorkspacesChanged()
}

export function createWorkspace(id: string): Workspace {
  const now = Date.now()

  return {
    id,
    title: DEFAULT_WORKSPACE_TITLE,
    createdAt: now,
    updatedAt: now,
  }
}

// ── Startup sync: load backend into in-memory cache ───────────

/**
 * Sync workspaces from backend into in-memory cache on app startup.
 */
export async function syncWorkspacesFromBackend(): Promise<number> {
  try {
    const backend = await listBackendWorkspaces()
    const cache = loadFromCache()
    let count = 0

    for (const w of backend) {
      if (!cache[w.id]) {
        const cached: Workspace = {
          id: w.id,
          title: w.title,
          createdAt: w.createdAt,
          updatedAt: w.updatedAt,
          hasSourceImage: w.hasSourceImage,
          currentVersionId: w.currentVersionId,
        }
        cache[w.id] = cached
        count++
      }
    }

    // Also sync last_workspace from backend
    try {
      const settings = await loadBackendSettings()
      if (settings.last_workspace) {
        lastWorkspaceId = settings.last_workspace
      }
    } catch {
      // ignore
    }

    if (count > 0) {
      // Preserve saves completed while settings were loading.
      saveToCache({ ...cache, ...loadFromCache() })
      notifySavedWorkspacesChanged()
    }

    return count
  } catch {
    return 0
  }
}
