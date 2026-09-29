function isImageFile(file: File): boolean {
  return file.type.startsWith('image/')
}

export function readImageFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
        return
      }

      reject(new Error('无法读取图片文件'))
    }
    reader.onerror = () => {
      reject(reader.error ?? new Error('无法读取图片文件'))
    }
    reader.readAsDataURL(file)
  })
}

export function pickImageFile(files: FileList | File[]): File | null {
  return Array.from(files).find(isImageFile) ?? null
}
