/**
 * Lightweight i18n for The Hiring Room
 * - Centralized translation keys
 * - localStorage persistence
 * - English fallback for missing keys
 * - Merges core + platform UI strings
 */

import { translations as core, SUPPORTED_LANGUAGES, LANGUAGE_NAMES } from './translations'
import { platformTranslations } from './platform'

const STORAGE_KEY = 'hiring_room_lang'

// Merge platform keys into each language (platform overrides only if key missing in core? prefer platform for same keys)
const translations = {}
for (const code of Object.keys(core)) {
  translations[code] = { ...(core[code] || {}), ...(platformTranslations[code] || {}) }
}
for (const code of Object.keys(platformTranslations)) {
  if (!translations[code]) translations[code] = { ...platformTranslations[code] }
}

export { SUPPORTED_LANGUAGES, LANGUAGE_NAMES, translations }

export function getStoredLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && translations[saved]) return saved
  } catch (_) {}
  return 'en'
}

export function setStoredLanguage(code) {
  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch (_) {}
}

export function t(key, lang = 'en', vars = {}) {
  const dict = translations[lang] || translations.en
  let str = dict[key]
  if (str == null || str === '') {
    str = translations.en[key]
  }
  if (str == null || str === '') {
    return key
  }
  if (vars && typeof vars === 'object') {
    Object.keys(vars).forEach((k) => {
      str = String(str).replace(new RegExp(`\\{${k}\\}`, 'g'), String(vars[k]))
    })
  }
  return str
}

export function languagePromptName(code) {
  const map = { en: 'English', hi: 'Hindi', kn: 'Kannada' }
  return map[code] || 'English'
}

export function speechLang(code) {
  const found = SUPPORTED_LANGUAGES.find((l) => l.code === code)
  return found?.speech || 'en-US'
}

/** Hook-friendly translator bound to a language */
export function useT(lang) {
  return (key, vars) => t(key, lang, vars)
}
