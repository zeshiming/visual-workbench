import { describe, expect, it } from 'vitest'

import { formatPageDocumentTitle } from '@/lib/sync-document-title'

describe('formatPageDocumentTitle', () => {
  it('joins page and site name with a pipe', () => {
    expect(formatPageDocumentTitle('主工作区', 'AI 图片创作工作台')).toBe('主工作区 | AI 图片创作工作台')
  })
})
