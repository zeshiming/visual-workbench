import logoUrl from '@/assets/images/logo.png'

export { logoUrl }

function upsertHeadLink(rel: string, href: string, type?: string): void {
  let link = document.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`)
  if (!link) {
    link = document.createElement('link')
    link.rel = rel
    document.head.appendChild(link)
  }

  if (type) link.type = type
  link.href = href
}

export function applyAppFavicon(href: string = logoUrl): void {
  upsertHeadLink('icon', href, 'image/png')
}

export function applyAppleTouchIcon(href: string = logoUrl): void {
  upsertHeadLink('apple-touch-icon', href)
}
