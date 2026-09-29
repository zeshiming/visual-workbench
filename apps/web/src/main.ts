import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { applyLocale, i18n } from '@/i18n'
import { applyAppleTouchIcon, applyAppFavicon } from '@/lib/app-brand'
import { loadLocale } from '@/lib/locale-storage'
import { applyTheme, loadTheme } from '@/lib/theme-storage'

applyTheme(loadTheme())
applyLocale(loadLocale())
applyAppFavicon()
applyAppleTouchIcon()

const app = createApp(App)

app.use(i18n)
app.use(router)

app.mount('#app')
