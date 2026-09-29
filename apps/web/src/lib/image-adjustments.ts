export type BasicImageAdjustments = {
  exposure: number
  contrast: number
  highlights: number
  shadows: number
  saturation: number
  temperature: number
  tint: number
}

export const DEFAULT_IMAGE_ADJUSTMENTS: BasicImageAdjustments = {
  exposure: 0,
  contrast: 0,
  highlights: 0,
  shadows: 0,
  saturation: 0,
  temperature: 0,
  tint: 0,
}

export type StylePresetId = 'natural' | 'warm-film' | 'cool-cinema' | 'soft-portrait'

export type CubeLut = {
  size: number
  values: Float32Array
}

export const STYLE_PRESETS: Array<{
  id: StylePresetId
  label: string
  description: string
  adjustments: BasicImageAdjustments
}> = [
  { id: 'natural', label: '自然', description: '还原中性层次', adjustments: { ...DEFAULT_IMAGE_ADJUSTMENTS } },
  {
    id: 'warm-film', label: '暖胶片', description: '暖色、柔和高光',
    adjustments: { ...DEFAULT_IMAGE_ADJUSTMENTS, contrast: 8, highlights: -12, shadows: 8, saturation: 8, temperature: 24, tint: 4 },
  },
  {
    id: 'cool-cinema', label: '冷电影', description: '冷色、压低高光',
    adjustments: { ...DEFAULT_IMAGE_ADJUSTMENTS, exposure: -4, contrast: 12, highlights: -20, shadows: 8, saturation: -5, temperature: -22, tint: -4 },
  },
  {
    id: 'soft-portrait', label: '柔和人像', description: '低对比、抑制高光',
    adjustments: { ...DEFAULT_IMAGE_ADJUSTMENTS, exposure: 6, contrast: -8, highlights: -18, shadows: 16, saturation: -8, temperature: 10, tint: 2 },
  },
]

function clampChannel(value: number): number {
  return Math.max(0, Math.min(255, value))
}

export function parseCubeLut(contents: string): CubeLut {
  let size = 0
  const values: number[] = []
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const parts = line.split(/\s+/)
    if (parts[0] === 'LUT_3D_SIZE') {
      size = Number(parts[1])
      continue
    }
    if (parts.length === 3 && parts.every((part) => Number.isFinite(Number(part)))) {
      values.push(Number(parts[0]), Number(parts[1]), Number(parts[2]))
    }
  }

  if (!Number.isInteger(size) || size < 2 || values.length !== size ** 3 * 3) {
    throw new Error('LUT 文件格式无效：需要完整的 LUT_3D_SIZE 数据')
  }
  return { size, values: new Float32Array(values) }
}

function lutIndex(size: number, red: number, green: number, blue: number): number {
  return (red + size * (green + size * blue)) * 3
}

export function applyCubeLut(source: AdjustmentSource, lut: CubeLut): string {
  const { width, height } = sourceSize(source)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建 LUT 处理画布')
  context.drawImage(source, 0, 0, width, height)
  const pixels = context.getImageData(0, 0, width, height)

  const sample = (r: number, g: number, b: number, channel: number): number => {
    const offset = lutIndex(lut.size, r, g, b) + channel
    return lut.values[offset] ?? 0
  }

  for (let index = 0; index < pixels.data.length; index += 4) {
    const values = [pixels.data[index]!, pixels.data[index + 1]!, pixels.data[index + 2]!]
      .map((value) => value / 255)
    const position = values.map((value) => value * (lut.size - 1))
    const low = position.map((value) => Math.floor(value))
    const high = position.map((value) => Math.min(lut.size - 1, Math.ceil(value)))
    const fraction = position.map((value, channel) => value - low[channel]!)

    for (let channel = 0; channel < 3; channel += 1) {
      const c000 = sample(low[0]!, low[1]!, low[2]!, channel)
      const c100 = sample(high[0]!, low[1]!, low[2]!, channel)
      const c010 = sample(low[0]!, high[1]!, low[2]!, channel)
      const c110 = sample(high[0]!, high[1]!, low[2]!, channel)
      const c001 = sample(low[0]!, low[1]!, high[2]!, channel)
      const c101 = sample(high[0]!, low[1]!, high[2]!, channel)
      const c011 = sample(low[0]!, high[1]!, high[2]!, channel)
      const c111 = sample(high[0]!, high[1]!, high[2]!, channel)
      const c00 = c000 + (c100 - c000) * fraction[0]!
      const c10 = c010 + (c110 - c010) * fraction[0]!
      const c01 = c001 + (c101 - c001) * fraction[0]!
      const c11 = c011 + (c111 - c011) * fraction[0]!
      const c0 = c00 + (c10 - c00) * fraction[1]!
      const c1 = c01 + (c11 - c01) * fraction[1]!
      pixels.data[index + channel] = clampChannel((c0 + (c1 - c0) * fraction[2]!) * 255)
    }
  }

  context.putImageData(pixels, 0, 0)
  return canvas.toDataURL('image/png')
}

export type AdjustmentSource = HTMLImageElement | HTMLCanvasElement

export function loadAdjustmentSource(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法读取图片进行调色'))
    image.src = source
  })
}

export function createAdjustmentPreviewSource(
  image: HTMLImageElement,
  maxDimension = 1400,
): AdjustmentSource {
  const width = image.naturalWidth || image.width
  const height = image.naturalHeight || image.height
  const scale = Math.min(1, maxDimension / Math.max(width, height))

  if (scale === 1) return image

  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(width * scale))
  canvas.height = Math.max(1, Math.round(height * scale))
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建调色预览画布')
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  return canvas
}

function sourceSize(source: AdjustmentSource): { width: number; height: number } {
  if (source instanceof HTMLImageElement) {
    return {
      width: source.naturalWidth || source.width,
      height: source.naturalHeight || source.height,
    }
  }

  return { width: source.width, height: source.height }
}

function clampAdjustment(value: number): number {
  return Math.max(-100, Math.min(100, Math.round(value)))
}

/** Estimate a neutral white balance using a sampled gray-world average. */
export function estimateAutoWhiteBalance(source: AdjustmentSource): Pick<BasicImageAdjustments, 'temperature' | 'tint'> {
  const { width, height } = sourceSize(source)
  const canvas = document.createElement('canvas')
  const sampleWidth = Math.min(width, 320)
  const sampleHeight = Math.max(1, Math.round((height / Math.max(width, 1)) * sampleWidth))
  canvas.width = sampleWidth
  canvas.height = sampleHeight

  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建白平衡分析画布')
  context.drawImage(source, 0, 0, sampleWidth, sampleHeight)
  const data = context.getImageData(0, 0, sampleWidth, sampleHeight).data

  let red = 0
  let green = 0
  let blue = 0
  let count = 0

  for (let index = 0; index < data.length; index += 4) {
    const r = data[index]!
    const g = data[index + 1]!
    const b = data[index + 2]!
    const luminance = r * 0.2126 + g * 0.7152 + b * 0.0722

    // Ignore transparent, near-black, and clipped-white pixels. They are
    // poor neutral references for a gray-world estimate.
    if (data[index + 3]! < 220 || luminance < 12 || luminance > 246) continue
    red += r
    green += g
    blue += b
    count += 1
  }

  if (!count) return { temperature: 0, tint: 0 }

  const averageRed = red / count
  const averageGreen = green / count
  const averageBlue = blue / count
  const neutral = (averageRed + averageGreen + averageBlue) / 3

  return {
    // Positive temperature adds red and removes blue in the renderer.
    temperature: clampAdjustment((averageBlue - averageRed) * 0.8),
    // Positive tint adds green; compensate when green is below the neutral mix.
    tint: clampAdjustment((neutral - averageGreen) * 0.8),
  }
}

export function computeLuminanceHistogram(source: AdjustmentSource, bins = 32): number[] {
  const { width, height } = sourceSize(source)
  const canvas = document.createElement('canvas')
  const sampleWidth = Math.min(width, 320)
  const sampleHeight = Math.max(1, Math.round((height / Math.max(width, 1)) * sampleWidth))
  canvas.width = sampleWidth
  canvas.height = sampleHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建直方图分析画布')
  context.drawImage(source, 0, 0, sampleWidth, sampleHeight)
  const data = context.getImageData(0, 0, sampleWidth, sampleHeight).data
  const histogram = Array.from({ length: bins }, () => 0)

  for (let index = 0; index < data.length; index += 4) {
    if (data[index + 3]! < 20) continue
    const luminance = Math.round(
      (data[index]! * 0.2126 + data[index + 1]! * 0.7152 + data[index + 2]! * 0.0722) / 255 * (bins - 1),
    )
    histogram[Math.max(0, Math.min(bins - 1, luminance))] += 1
  }

  const maximum = Math.max(...histogram, 1)
  return histogram.map((value) => value / maximum)
}

function channelStats(source: AdjustmentSource): { mean: number[]; deviation: number[] } {
  const { width, height } = sourceSize(source)
  const canvas = document.createElement('canvas')
  const sampleWidth = Math.min(width, 320)
  const sampleHeight = Math.max(1, Math.round((height / Math.max(width, 1)) * sampleWidth))
  canvas.width = sampleWidth
  canvas.height = sampleHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建颜色分析画布')
  context.drawImage(source, 0, 0, sampleWidth, sampleHeight)
  const data = context.getImageData(0, 0, sampleWidth, sampleHeight).data
  const sums = [0, 0, 0]
  const squares = [0, 0, 0]
  let count = 0

  for (let index = 0; index < data.length; index += 4) {
    if (data[index + 3]! < 20) continue
    for (let channel = 0; channel < 3; channel += 1) {
      const value = data[index + channel]!
      sums[channel] += value
      squares[channel] += value * value
    }
    count += 1
  }

  const mean = sums.map((value) => (count ? value / count : 128))
  const deviation = squares.map((value, index) => Math.sqrt(Math.max(1, value / Math.max(count, 1) - mean[index]! ** 2)))
  return { mean, deviation }
}

/** Reinhard-style RGB color transfer for a local reference-image match. */
export function applyReferenceColorTransfer(
  target: AdjustmentSource,
  reference: AdjustmentSource,
): string {
  const { width, height } = sourceSize(target)
  const targetStats = channelStats(target)
  const referenceStats = channelStats(reference)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建追色画布')
  context.drawImage(target, 0, 0, width, height)
  const pixels = context.getImageData(0, 0, width, height)

  for (let index = 0; index < pixels.data.length; index += 4) {
    for (let channel = 0; channel < 3; channel += 1) {
      const value = pixels.data[index + channel]!
      const normalized = (value - targetStats.mean[channel]!) / targetStats.deviation[channel]!
      pixels.data[index + channel] = clampChannel(
        normalized * referenceStats.deviation[channel]! + referenceStats.mean[channel]!,
      )
    }
  }

  context.putImageData(pixels, 0, 0)
  return canvas.toDataURL('image/png')
}

/** Apply deterministic, local pixel adjustments. No network or AI call is made. */
export function renderBasicImageAdjustments(
  source: AdjustmentSource,
  adjustments: BasicImageAdjustments,
): string {
  const { width, height } = sourceSize(source)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const context = canvas.getContext('2d')
  if (!context || canvas.width === 0 || canvas.height === 0) {
    throw new Error('无法创建图片调色画布')
  }

  context.drawImage(source, 0, 0, width, height)
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
  const data = pixels.data
  const exposureFactor = 2 ** (adjustments.exposure / 100)
  const contrastValue = adjustments.contrast * 2.55
  const contrastFactor =
    (259 * (contrastValue + 255)) / (255 * (259 - contrastValue))
  const saturationFactor = 1 + adjustments.saturation / 100
  const temperatureShift = adjustments.temperature * 0.85
  const tintShift = adjustments.tint * 0.28

  for (let index = 0; index < data.length; index += 4) {
    let red = data[index]! * exposureFactor
    let green = data[index + 1]! * exposureFactor
    let blue = data[index + 2]! * exposureFactor

    red += temperatureShift
    blue -= temperatureShift
    green += tintShift
    red -= tintShift * 0.35
    blue -= tintShift * 0.35

    red = contrastFactor * (red - 128) + 128
    green = contrastFactor * (green - 128) + 128
    blue = contrastFactor * (blue - 128) + 128

    const luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
    const normalizedLuminance = luminance / 255
    const highlightWeight = Math.max(0, (normalizedLuminance - 0.5) * 2)
    const shadowWeight = Math.max(0, (0.5 - normalizedLuminance) * 2)
    const tonalShift =
      (adjustments.highlights * highlightWeight + adjustments.shadows * shadowWeight) * 0.45
    red += tonalShift
    green += tonalShift
    blue += tonalShift
    const adjustedLuminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
    red = adjustedLuminance + (red - adjustedLuminance) * saturationFactor
    green = adjustedLuminance + (green - adjustedLuminance) * saturationFactor
    blue = adjustedLuminance + (blue - adjustedLuminance) * saturationFactor

    data[index] = clampChannel(red)
    data[index + 1] = clampChannel(green)
    data[index + 2] = clampChannel(blue)
  }

  context.putImageData(pixels, 0, 0)
  return canvas.toDataURL('image/png')
}

export async function applyBasicImageAdjustments(
  source: string,
  adjustments: BasicImageAdjustments,
): Promise<string> {
  return renderBasicImageAdjustments(await loadAdjustmentSource(source), adjustments)
}
