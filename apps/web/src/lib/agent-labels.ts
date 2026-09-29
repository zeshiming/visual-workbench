import type { DeficiencyCategory, ImageType } from '@/types/agent'

import { translate } from '@/i18n'

export function getImageTypeLabel(type: ImageType): string {
  return translate(`agent.imageType.${type}`)
}

export function getDeficiencyCategoryLabel(category: DeficiencyCategory): string {
  return translate(`agent.deficiency.${category}`)
}

export function getDeficiencySeverityLabel(severity: 'low' | 'medium' | 'high'): string {
  return translate(`agent.severity.${severity}`)
}
