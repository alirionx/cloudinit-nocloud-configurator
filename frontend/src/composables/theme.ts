// FR-016: light/dark theme, light by default, remembered in local storage.
import { useTheme } from 'vuetify'

export type ThemeName = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'cnc-theme'

/** The stored theme; light if nothing (or something invalid) is stored. */
export function storedTheme(): ThemeName {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function useThemeSwitch() {
  const theme = useTheme()

  function setTheme(name: ThemeName) {
    theme.change(name)
    document.documentElement.dataset.theme = name
    try {
      localStorage.setItem(THEME_STORAGE_KEY, name)
    } catch {
      // Storage unavailable (private mode): the choice lasts for this page only.
    }
  }

  function toggle() {
    setTheme(theme.global.current.value.dark ? 'light' : 'dark')
  }

  return { theme, setTheme, toggle }
}
