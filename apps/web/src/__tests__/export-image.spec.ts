import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildExportFilename,
  downloadDataUrl,
  getImageExtensionFromDataUrl,
  sanitizeExportFilename,
} from '../lib/export-image'

describe('export-image', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('maps common image mime subtypes to file extensions', () => {
    expect(getImageExtensionFromDataUrl('data:image/png;base64,abc')).toBe('png')
    expect(getImageExtensionFromDataUrl('data:image/jpeg;base64,abc')).toBe('jpg')
    expect(getImageExtensionFromDataUrl('data:image/webp;base64,abc')).toBe('webp')
    expect(getImageExtensionFromDataUrl('data:image/svg+xml;base64,abc')).toBe('svg')
    expect(getImageExtensionFromDataUrl('invalid')).toBe('png')
  })

  it('sanitizes unsafe filename characters', () => {
    expect(sanitizeExportFilename('  我的/图片  ')).toBe('我的-图片')
    expect(sanitizeExportFilename('<>:"|?*')).toBe('-------')
    expect(sanitizeExportFilename('   ')).toBe('image')
  })

  it('builds export filename from workspace title and image type', () => {
    expect(buildExportFilename('风景修图', 'data:image/jpeg;base64,abc')).toBe('风景修图.jpg')
  })

  it('downloads image via temporary object url', async () => {
    const blob = new Blob(['image-bytes'], { type: 'image/png' })
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(blob))

    const createObjectURL = vi.fn(() => 'blob:mock-url')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })

    const click = vi.fn()
    const link = {
      click,
      href: '',
      download: '',
      rel: '',
    } as unknown as HTMLAnchorElement
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node)
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node)
    vi.spyOn(document, 'createElement').mockReturnValue(link)

    await downloadDataUrl('data:image/png;base64,abc', 'test.png')

    expect(fetch).toHaveBeenCalledWith('data:image/png;base64,abc')
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(link.download).toBe('test.png')
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    expect(appendChild).toHaveBeenCalled()
    expect(removeChild).toHaveBeenCalled()
  })
})
