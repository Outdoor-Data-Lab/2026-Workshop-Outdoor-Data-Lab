/** Traductions de l'interface. Une langue par instance : `VITE_LOCALE` (`en` par défaut). */
import { createI18n } from 'vue-i18n'

import en from './locales/en'
import fr from './locales/fr'

const locale = import.meta.env.VITE_LOCALE ?? 'en'

export const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'en',
  messages: { en, fr },
})

document.documentElement.lang = locale

/** Libellé d'une valeur de référence de l'API : traduction de son code, sinon le libellé reçu. */
export function referenceLabel(table: string, code: string, label: string): string {
  const key = `${table}.${code}`
  return i18n.global.te(key) ? i18n.global.t(key) : label
}
