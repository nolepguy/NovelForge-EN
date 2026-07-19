import './assets/main.css'

import { setupWebMock } from './web-mock'
setupWebMock()

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import i18n from './i18n'
import { useAppStore } from './stores/useAppStore'
import { usePerCardAISettingsStore } from './stores/usePerCardAISettingsStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(i18n)
app.use(ElementPlus)

// Initialize theme (must happen before mounting)
const appStore = useAppStore()
appStore.initTheme()
appStore.initLocale()

// --- Load initial data ---
const perCardStore = usePerCardAISettingsStore()
perCardStore.loadFromLocal()

app.mount('#app')
