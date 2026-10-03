import { watchEffect } from 'vue'

/** vue-i18n 会把 `|` 当作复数分支，标题须在代码里拼接 */
export function formatPageDocumentTitle(page: string, siteName: string): string {
  return `${page} | ${siteName}`
}

export function syncDocumentTitle(options: {
  appName: () => string
  pageTitle: () => string
}): void {
  watchEffect(() => {
    document.title = formatPageDocumentTitle(options.pageTitle(), options.appName())
  })
}
