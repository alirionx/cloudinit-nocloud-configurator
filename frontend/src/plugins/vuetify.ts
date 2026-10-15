import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import { storedTheme } from '../composables/theme'

// Colors are chosen for WCAG 2.1 AA contrast in both themes (NFR-013).
export function createAppVuetify() {
  return createVuetify({
    theme: {
      defaultTheme: storedTheme(),
      themes: {
        light: {
          dark: false,
          // Labels and secondary text: higher than Vuetify's default for 4.5:1 contrast.
          variables: { 'medium-emphasis-opacity': 0.68 },
          colors: {
            background: '#ffffff',
            surface: '#ffffff',
            'surface-variant': '#eef1f5',
            primary: '#1565c0',
            secondary: '#455a64',
            error: '#b00020',
            warning: '#8a5300',
            info: '#0d5ea8',
            success: '#1b6e20',
          },
        },
        dark: {
          dark: true,
          variables: { 'medium-emphasis-opacity': 0.75 },
          colors: {
            background: '#121212',
            surface: '#1e1e1e',
            'surface-variant': '#2a2d31',
            primary: '#90caf9',
            secondary: '#b0bec5',
            error: '#ff8a80',
            warning: '#ffcc80',
            info: '#81d4fa',
            success: '#a5d6a7',
          },
        },
      },
    },
    icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
    defaults: {
      VTextField: { variant: 'outlined', density: 'compact' },
      VTextarea: { variant: 'outlined', density: 'compact' },
      VSelect: { variant: 'outlined', density: 'compact' },
      VCombobox: { variant: 'outlined', density: 'compact' },
      VAutocomplete: { variant: 'outlined', density: 'compact' },
      VCheckbox: { density: 'compact', hideDetails: 'auto' },
      VSwitch: { density: 'compact', hideDetails: 'auto', color: 'primary', inset: true },
    },
  })
}
