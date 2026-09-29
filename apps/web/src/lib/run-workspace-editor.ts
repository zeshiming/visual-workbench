/**
 * Thin wrapper that bridges the workspace layer to the backend API.
 * The Python backend handles: prompt building, AI calls, image normalization.
 */
import { translate } from '@/i18n'

import { validateRunConfig } from '@/lib/app-settings'
import { generateImageViaBackend, type EditorMarkData } from '@/lib/api-client'
import { loadAppSettings } from '@/lib/config-storage'
import { hydrateWorkspaceImage } from '@/lib/workspace-storage'
import type { EditorMark } from '@/types/editor-mark'
import type { ModelSelection } from '@/types/app-settings'
import type { Workspace } from '@/types/workspace'

export async function runWorkspaceEditor(
  workspace: Workspace,
  marks: EditorMark[],
  modelSelection?: ModelSelection,
): Promise<string> {
  if (marks.length === 0) {
    throw new Error(translate('errors.markAreaFirst'))
  }

  const settings = loadAppSettings()
  const config = validateRunConfig(settings, modelSelection)

  const hydrated = await hydrateWorkspaceImage(workspace)

  if (!hydrated.sourceImage) {
    throw new Error(translate('errors.uploadImageFirst'))
  }

  // Send marks to backend — the backend builds the full prompt
  const marksData: EditorMarkData[] = marks.map((m) => ({
    center_x: m.centerX,
    center_y: m.centerY,
    radius: m.radius,
    description: m.description,
  }))

  const result = await generateImageViaBackend(
    config,
    hydrated.sourceImage,
    marksData,
  )

  const nextImage = result.images[0]

  if (!nextImage) {
    throw new Error(translate('errors.editModelNoImage'))
  }

  return nextImage
}
