const DATA_URL_MIME_PATTERN = /^data:image\/([\w+.-]+);/

export function getImageExtensionFromDataUrl(dataUrl: string): string {
  const match = dataUrl.match(DATA_URL_MIME_PATTERN)
  if (!match) {
    return 'png'
  }

  const subtype = match[1]!.toLowerCase()
  if (subtype === 'jpeg') {
    return 'jpg'
  }

  if (subtype === 'svg+xml') {
    return 'svg'
  }

  return subtype
}

export function sanitizeExportFilename(name: string): string {
  const sanitized = name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').trim()
  return sanitized || 'image'
}

export function buildExportFilename(title: string, dataUrl: string): string {
  const extension = getImageExtensionFromDataUrl(dataUrl)
  return `${sanitizeExportFilename(title)}.${extension}`
}

export async function downloadDataUrl(dataUrl: string, filename: string): Promise<void> {
  const response = await fetch(dataUrl)
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)

  try {
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export async function exportImage(dataUrl: string, title: string): Promise<void> {
  await downloadDataUrl(dataUrl, buildExportFilename(title, dataUrl))
}
