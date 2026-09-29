import { beforeEach, describe, expect, it } from 'vitest'

import {
  addOpenWorkspace,
  addSettingsTab,
  clearDraftWorkspaces,
  closeTab,
  closeWorkspaceTab,
  createDraftWorkspace,
  deleteSavedWorkspace,
  getWorkspace,
  isDefaultWorkspace,
  isSettingsTab,
  isWorkspaceDirty,
  openTabs,
  openWorkspaces,
  persistWorkspace,
  removeSavedProject,
  applyWorkspaceGeneratedImage,
  canUndoWorkspaceImage,
  undoWorkspaceImageChange,
  SETTINGS_TAB_ID,
  stageWorkspaceChanges,
  stageWorkspaceGeneratedImage,
} from '../lib/workspace-session'
import {
  clearWorkspaceCache,
  createWorkspace,
  hydrateWorkspaceImage,
  loadSavedProjectsFromLocalStorage,
  loadWorkspace,
  saveWorkspace,
} from '../lib/workspace-storage'
import { clearWorkspaceImages } from '../lib/workspace-image-storage'

describe('workspace-session', () => {
  beforeEach(() => {
    clearWorkspaceCache()
    clearWorkspaceImages()
    clearDraftWorkspaces()
  })

  it('keeps a new workspace in memory only', () => {
    createDraftWorkspace('workspace-1')

    expect(getWorkspace('workspace-1')).toBeTruthy()
  })

  it('tracks multiple open workspaces in tab order', () => {
    createDraftWorkspace('workspace-1')
    createDraftWorkspace('workspace-2')

    expect(openWorkspaces.value.map((workspace) => workspace.id)).toEqual([
      'workspace-1',
      'workspace-2',
    ])
  })

  it('persists a workspace after it has been changed', async () => {
    const draft = createDraftWorkspace('workspace-1')
    const changed = {
      ...draft,
      title: '我的设计',
    }

    await persistWorkspace(changed)

    expect(loadWorkspace('workspace-1')).toEqual({
      ...changed,
      updatedAt: expect.any(Number),
    })
    expect(getWorkspace('workspace-1')).toEqual(loadWorkspace('workspace-1'))
    expect(isWorkspaceDirty('workspace-1')).toBe(false)
  })

  it('marks staged workspace changes as dirty until saved', async () => {
    const draft = createDraftWorkspace('workspace-1')

    stageWorkspaceChanges({
      ...draft,
      sourceImage: 'data:image/png;base64,abc',
    })

    expect(isWorkspaceDirty('workspace-1')).toBe(true)

    await persistWorkspace({
      ...getWorkspace('workspace-1')!,
      title: '海报草稿',
    })

    expect(isWorkspaceDirty('workspace-1')).toBe(false)
    expect(loadWorkspace('workspace-1')?.title).toBe('海报草稿')

    const hydrated = await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)
    expect(hydrated.sourceImage).toBe('data:image/png;base64,abc')
  })

  it('detects the default unnamed workspace', () => {
    const draft = createWorkspace('workspace-1')

    expect(isDefaultWorkspace(draft)).toBe(true)
    expect(
      isDefaultWorkspace({
        ...draft,
        title: '已修改',
      }),
    ).toBe(false)
  })

  it('closes a draft without leaving data', () => {
    createDraftWorkspace('workspace-1')

    closeWorkspaceTab('workspace-1')

    expect(getWorkspace('workspace-1')).toBeNull()
  })

  it('keeps saved projects when closing a tab', async () => {
    const workspace = createWorkspace('workspace-1')
    await saveWorkspace({
      ...workspace,
      title: '已保存项目',
    })
    addOpenWorkspace('workspace-1')

    closeWorkspaceTab('workspace-1')

    expect(loadWorkspace('workspace-1')?.title).toBe('已保存项目')
    expect(loadSavedProjectsFromLocalStorage()).toHaveLength(1)
  })

  it('deletes a saved project', async () => {
    const workspace = createWorkspace('workspace-1')
    await saveWorkspace(workspace)

    await removeSavedProject('workspace-1')

    expect(loadWorkspace('workspace-1')).toBeNull()
  })

  it('closes an open tab when deleting a saved project', async () => {
    const workspace = createWorkspace('workspace-1')
    await saveWorkspace(workspace)
    addOpenWorkspace('workspace-1')

    const nextId = await removeSavedProject('workspace-1')

    expect(nextId).toBeNull()
    expect(getWorkspace('workspace-1')).toBeNull()
    expect(openWorkspaces.value).toHaveLength(0)
  })

  it('stages generated image until the workspace is saved', async () => {
    const draft = createDraftWorkspace('workspace-1')
    const originalImage = 'data:image/png;base64,original'
    const editedImage = 'data:image/png;base64,edited'

    await saveWorkspace({
      ...draft,
      sourceImage: originalImage,
      hasSourceImage: true,
    })

    await applyWorkspaceGeneratedImage(
      {
        ...draft,
        sourceImage: originalImage,
        hasSourceImage: true,
      },
      editedImage,
    )

    expect(getWorkspace('workspace-1')?.sourceImage).toBe(editedImage)
    expect(isWorkspaceDirty('workspace-1')).toBe(true)
    expect(await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)).toMatchObject({
      sourceImage: originalImage,
    })

    await persistWorkspace({
      ...getWorkspace('workspace-1')!,
      title: '已保存项目',
    })

    expect(isWorkspaceDirty('workspace-1')).toBe(false)
    expect(await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)).toMatchObject({
      sourceImage: editedImage,
    })
  })

  it('undoes the latest image change without persisting until saved', async () => {
    const draft = createDraftWorkspace('workspace-1')
    const originalImage = 'data:image/png;base64,original'
    const editedImage = 'data:image/png;base64,edited'

    await saveWorkspace({
      ...draft,
      sourceImage: originalImage,
      hasSourceImage: true,
    })

    await applyWorkspaceGeneratedImage(
      {
        ...draft,
        sourceImage: originalImage,
        hasSourceImage: true,
      },
      editedImage,
    )

    const restored = await undoWorkspaceImageChange('workspace-1')

    expect(restored?.sourceImage).toBe(originalImage)
    expect(isWorkspaceDirty('workspace-1')).toBe(true)
    expect(await hydrateWorkspaceImage(loadWorkspace('workspace-1')!)).toMatchObject({
      sourceImage: originalImage,
    })
  })

  it('clears undo history when closing a workspace tab', async () => {
    const draft = createDraftWorkspace('workspace-1')

    await saveWorkspace({
      ...draft,
      sourceImage: 'data:image/png;base64,original',
      hasSourceImage: true,
    })

    await applyWorkspaceGeneratedImage(
      {
        ...draft,
        sourceImage: 'data:image/png;base64,original',
        hasSourceImage: true,
      },
      'data:image/png;base64,edited',
    )

    expect(canUndoWorkspaceImage('workspace-1')).toBe(true)

    closeWorkspaceTab('workspace-1')

    expect(canUndoWorkspaceImage('workspace-1')).toBe(false)
  })

  it('starts with empty undo history when reopening a closed workspace tab', async () => {
    const draft = createDraftWorkspace('workspace-1')

    await saveWorkspace({
      ...draft,
      sourceImage: 'data:image/png;base64,original',
      hasSourceImage: true,
    })

    await applyWorkspaceGeneratedImage(
      {
        ...draft,
        sourceImage: 'data:image/png;base64,original',
        hasSourceImage: true,
      },
      'data:image/png;base64,edited',
    )

    closeWorkspaceTab('workspace-1')
    addOpenWorkspace('workspace-1')

    expect(canUndoWorkspaceImage('workspace-1')).toBe(false)
  })

  it('stages generated image for workspace display', () => {
    const draft = createDraftWorkspace('workspace-1')

    stageWorkspaceGeneratedImage(
      {
        ...draft,
        sourceImage: 'data:image/png;base64,original',
        hasSourceImage: true,
      },
      'data:image/png;base64,edited',
    )

    expect(getWorkspace('workspace-1')?.sourceImage).toBe('data:image/png;base64,edited')
    expect(isWorkspaceDirty('workspace-1')).toBe(true)
  })

  it('closes a tab and switches to the neighboring workspace', () => {
    createDraftWorkspace('workspace-1')
    createDraftWorkspace('workspace-2')
    createDraftWorkspace('workspace-3')

    const nextId = closeWorkspaceTab('workspace-2')

    expect(nextId).toBe('workspace-3')
    expect(openWorkspaces.value.map((workspace) => workspace.id)).toEqual([
      'workspace-1',
      'workspace-3',
    ])
    expect(getWorkspace('workspace-2')).toBeNull()
  })

  it('tracks the settings tab alongside workspace tabs', () => {
    createDraftWorkspace('workspace-1')
    addSettingsTab()

    expect(openTabs.value).toEqual(['workspace-1', SETTINGS_TAB_ID])
    expect(isSettingsTab(SETTINGS_TAB_ID)).toBe(true)
    expect(openWorkspaces.value.map((workspace) => workspace.id)).toEqual(['workspace-1'])
  })

  it('closes the settings tab without affecting workspaces', () => {
    createDraftWorkspace('workspace-1')
    addSettingsTab()

    const nextId = closeTab(SETTINGS_TAB_ID)

    expect(nextId).toBe('workspace-1')
    expect(openTabs.value).toEqual(['workspace-1'])
    expect(getWorkspace('workspace-1')).toBeTruthy()
  })
})
