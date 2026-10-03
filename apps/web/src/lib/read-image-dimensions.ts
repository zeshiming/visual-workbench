/**
 * Read image dimensions from a data URL without DOM Image element.
 * Works in both browser and test environments.
 */
export function readImageDimensionsFromFile(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    try {
      const dimensions = parseImageDimensions(dataUrl)
      resolve(dimensions)
    } catch (err) {
      reject(err instanceof Error ? err : new Error('Failed to read image dimensions'))
    }
  })
}

function u8(bytes: Uint8Array, offset: number): number {
  return bytes[offset]!
}

function u16be(bytes: Uint8Array, offset: number): number {
  return (bytes[offset]! << 8) | bytes[offset + 1]!
}

function u32be(bytes: Uint8Array, offset: number): number {
  return (
    (bytes[offset]! << 24) |
    (bytes[offset + 1]! << 16) |
    (bytes[offset + 2]! << 8) |
    bytes[offset + 3]!
  ) >>> 0
}

function u16le(bytes: Uint8Array, offset: number): number {
  return bytes[offset]! | (bytes[offset + 1]! << 8)
}

/**
 * Parse image dimensions from a data URL by reading encoded bytes.
 * Supports PNG, JPEG, WebP, GIF, and BMP formats.
 */
export function parseImageDimensions(dataUrl: string): { width: number; height: number } {
  const commaIndex = dataUrl.indexOf(',')
  if (commaIndex === -1) {
    throw new Error('Invalid data URL')
  }
  const base64 = dataUrl.slice(commaIndex + 1)
  const binaryStr = atob(base64)
  const len = binaryStr.length
  const bytes = new Uint8Array(len)
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryStr.charCodeAt(i)
  }

  // PNG: width/height at bytes 16-23 (big-endian)
  if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) {
    return { width: u32be(bytes, 16), height: u32be(bytes, 20) }
  }

  // JPEG: scan for SOF markers (0xFF 0xC0/0xC1/0xC2)
  if (bytes[0] === 0xff && bytes[1] === 0xd8) {
    let offset = 2
    while (offset < len - 1) {
      if (bytes[offset] !== 0xff) {
        offset++
        continue
      }
      const marker = bytes[offset + 1]
      if (marker === 0xc0 || marker === 0xc1 || marker === 0xc2) {
        return { width: u16be(bytes, offset + 7), height: u16be(bytes, offset + 5) }
      }
      offset += 2 + u16be(bytes, offset + 2)
    }
    throw new Error('Could not find JPEG dimensions')
  }

  // WebP: read VP8/VP8L/VP8X header
  if (bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46) {
    if (
      bytes[8] === 0x57 && bytes[9] === 0x45 &&
      bytes[10] === 0x42 && bytes[11] === 0x50
    ) {
      const chunkType = String.fromCharCode(bytes[12]!, bytes[13]!, bytes[14]!, bytes[15]!)
      if (chunkType === 'VP8 ' && len >= 30) {
        const w = (u16le(bytes, 26) & 0x3fff)
        const h = (u16le(bytes, 28) & 0x3fff)
        return { width: w, height: h }
      }
      if (chunkType === 'VP8L' && len >= 25) {
        const bits = u32be(bytes, 21)
        return { width: (bits & 0x3fff) + 1, height: ((bits >> 14) & 0x3fff) + 1 }
      }
      if (chunkType === 'VP8X' && len >= 30) {
        const w = ((bytes[24]! | (bytes[25]! << 8) | (bytes[26]! << 16)) >>> 0) + 1
        const h = ((bytes[27]! | (bytes[28]! << 8) | (bytes[29]! << 16)) >>> 0) + 1
        return { width: w, height: h }
      }
    }
    throw new Error('Unsupported WebP format')
  }

  // GIF: width/height at bytes 6-9 (little-endian)
  if (bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
    return { width: u16le(bytes, 6), height: u16le(bytes, 8) }
  }

  // BMP: width/height at bytes 18-25 (little-endian)
  if (bytes[0] === 0x42 && bytes[1] === 0x4d) {
    const w = u32be(bytes, 18)
    const h = u32be(bytes, 22)
    return { width: w, height: h }
  }

  throw new Error('Unsupported or unrecognized image format')
}
