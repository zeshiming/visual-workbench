export type Workspace = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  sourceImage?: string
  hasSourceImage?: boolean
}

export type WorkspaceTabItem = {
  id: string
  title: string
  isDirty: boolean
}
