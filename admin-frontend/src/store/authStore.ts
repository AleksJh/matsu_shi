import { create } from 'zustand'

const STORAGE_KEY = 'admin_jwt'

export function isJwtExpired(jwt: string): boolean {
  try {
    const payload = JSON.parse(atob(jwt.split('.')[1]))
    return payload.exp < Date.now() / 1000
  } catch {
    return true
  }
}

interface AuthState {
  jwt: string | null
  setAuth: (jwt: string) => void
  clearAuth: () => void
}

const stored = localStorage.getItem(STORAGE_KEY)
const initial: string | null = stored && !isJwtExpired(stored) ? stored : null

export const useAuthStore = create<AuthState>()((set) => ({
  jwt: initial,
  setAuth: (jwt) => {
    localStorage.setItem(STORAGE_KEY, jwt)
    set({ jwt })
  },
  clearAuth: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ jwt: null })
  },
}))
