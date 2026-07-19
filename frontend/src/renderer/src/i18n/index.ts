import { createI18n } from 'vue-i18n'

export type AppLocale = 'en' | 'zh-CN'

const STORAGE_KEY = 'app-language'

export function getStoredLocale(): AppLocale {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'zh-CN' || saved === 'en') return saved
  return 'en'
}

export function storeLocale(locale: AppLocale): void {
  localStorage.setItem(STORAGE_KEY, locale)
}

const enModules = import.meta.glob('../locales/en/*.json', { eager: true, import: 'default' }) as Record<string, Record<string, unknown>>
const zhModules = import.meta.glob('../locales/zh-CN/*.json', { eager: true, import: 'default' }) as Record<string, Record<string, unknown>>

function mergeMessages(modules: Record<string, Record<string, unknown>>): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const mod of Object.values(modules)) {
    for (const [key, value] of Object.entries(mod)) {
      result[key] = value
    }
  }
  return result
}

const i18n = createI18n({
  legacy: false,
  locale: getStoredLocale(),
  fallbackLocale: 'en',
  messages: {
    en: mergeMessages(enModules),
    'zh-CN': mergeMessages(zhModules)
  } as Record<string, any>
})

export default i18n
