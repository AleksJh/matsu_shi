import { create } from 'zustand'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'ms-theme'

function getInitialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

// Apply immediately to avoid flash on load
const initialTheme = getInitialTheme()
document.body.setAttribute('data-theme', initialTheme)

interface ThemeState {
  theme: Theme
  toggle: () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: initialTheme,
  toggle: () => {
    const next: Theme = get().theme === 'light' ? 'dark' : 'light'
    localStorage.setItem(STORAGE_KEY, next)
    document.body.setAttribute('data-theme', next)
    set({ theme: next })
  },
}))
