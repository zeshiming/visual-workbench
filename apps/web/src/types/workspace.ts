export type Workspace = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  sourceImage?: string
  hasSourceImage?: boolean
  currentVersionId?: string | null
  draftParentVersionId?: string | null
  pendingEditorRunId?: string | null
  pendingAssetId?: string | null
}

export type WorkspaceTabItem = {
  id: string
  title: string
  isDirty: boolean
}
