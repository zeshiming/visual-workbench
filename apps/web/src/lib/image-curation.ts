export type CurationScore = {
  score: number
  sharpness: number
  exposure: number
  contrast: number
  hash: string
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

export async function scoreImageForCuration(source: string): Promise<CurationScore> {
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const next = new Image()
    next.onload = () => resolve(next)
    next.onerror = () => reject(new Error('无法读取照片进行选片分析'))
    next.src = source
  })

  const width = Math.min(image.naturalWidth || image.width, 240)
  const height = Math.max(1, Math.round((image.naturalHeight / Math.max(image.naturalWidth, 1)) * width))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建选片分析画布')
  context.drawImage(image, 0, 0, width, height)
  const pixels = context.getImageData(0, 0, width, height).data
  const luminance = new Float32Array(width * height)
  let mean = 0

  for (let index = 0, pixel = 0; index < pixels.length; index += 4, pixel += 1) {
    const value = (pixels[index]! * 0.2126 + pixels[index + 1]! * 0.7152 + pixels[index + 2]! * 0.0722) / 255
    luminance[pixel] = value
    mean += value
  }

  mean /= Math.max(luminance.length, 1)
  let variance = 0
  let edgeEnergy = 0
  let hash = ''
  const hashSize = 8
  for (let y = 0; y < hashSize; y += 1) {
    for (let x = 0; x < hashSize; x += 1) {
      const sampleX = Math.min(width - 1, Math.floor((x + 0.5) * width / hashSize))
      const sampleY = Math.min(height - 1, Math.floor((y + 0.5) * height / hashSize))
      hash += luminance[sampleY * width + sampleX]! > mean ? '1' : '0'
    }
  }
  for (let y = 1; y < height; y += 1) {
    for (let x = 1; x < width; x += 1) {
      const index = y * width + x
      const value = luminance[index]!
      const left = luminance[index - 1]!
      const above = luminance[index - width]!
      variance += (value - mean) ** 2
      edgeEnergy += Math.abs(value - left) + Math.abs(value - above)
    }
  }

  const contrast = clamp(Math.sqrt(variance / Math.max(luminance.length, 1)) / 0.28)
  const exposure = clamp(1 - Math.abs(mean - 0.5) / 0.5)
  const sharpness = clamp((edgeEnergy / Math.max((width - 1) * (height - 1), 1)) / 0.24)
  const score = Math.round((sharpness * 0.45 + exposure * 0.3 + contrast * 0.25) * 100)

  return { score, sharpness, exposure, contrast, hash }
}
