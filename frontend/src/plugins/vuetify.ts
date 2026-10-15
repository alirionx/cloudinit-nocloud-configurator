import '@fontsource-variable/inter'
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import { storedTheme } from '../composables/theme'

// Visual style (section 7.2): near-black dark theme as default (FR-016), mint/teal accent,
// salmon as secondary color. Colors are chosen for WCAG 2.1 AA contrast (NFR-013).
export function createAppVuetify() {
  return createVuetify({
    theme: {
      defaultTheme: storedTheme(),
      themes: {
        dark: {
          dark: true,
          variables: { 'medium-emphasis-opacity': 0.72, 'border-opacity': 0.14 },
          colors: {
            background: '#0e0f12',
            surface: '#16181c',
            'surface-bright': '#1d2025',
            'surface-variant': '#22252b',
            'on-surface-variant': '#e6e8eb',
            primary: '#3ddbc0',
            'on-primary': '#04211c',
            secondary: '#ff8f7a',
            'on-secondary': '#2b0c06',
            error: '#ff7b72',
            'on-error': '#2b0806',
            warning: '#ffc46b',
            'on-warning': '#2b1d04',
            info: '#7cc8ff',
            'on-info': '#04202f',
            success: '#3ddbc0',
            'on-success': '#04211c',
          },
        },
        light: {
          dark: false,
          variables: { 'medium-emphasis-opacity': 0.7, 'border-opacity': 0.14 },
          colors: {
            background: '#f5f6f8',
            surface: '#ffffff',
            'surface-bright': '#ffffff',
            'surface-variant': '#eceff3',
            'on-surface-variant': '#1d2025',
            primary: '#00796b',
            'on-primary': '#ffffff',
            secondary: '#b5412c',
            'on-secondary': '#ffffff',
            error: '#b3261e',
            warning: '#8a5300',
            info: '#0b63a8',
            success: '#1b6e20',
          },
        },
      },
    },
    icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
    defaults: {
      global: { ripple: true },
      VBtn: { rounded: 'pill', class: 'text-none font-weight-medium' },
      VCard: { rounded: 'lg' },
      VAlert: { rounded: 'lg' },
      VChip: { rounded: 'pill' },
      VTextField: { variant: 'outlined', density: 'compact', rounded: 'lg' },
      VTextarea: { variant: 'outlined', density: 'compact', rounded: 'lg' },
      VSelect: { variant: 'outlined', density: 'compact', rounded: 'lg' },
      VCombobox: { variant: 'outlined', density: 'compact', rounded: 'lg' },
      VAutocomplete: { variant: 'outlined', density: 'compact', rounded: 'lg' },
      VCheckbox: { density: 'compact', hideDetails: 'auto', color: 'primary' },
      VSwitch: { density: 'compact', hideDetails: 'auto', color: 'primary', inset: true },
      VTabs: { color: 'primary' },
    },
  })
}
