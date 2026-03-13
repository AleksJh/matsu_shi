import { create } from 'zustand'
import type { Session } from '../types'

interface SessionState {
  sessions: Session[]
  activeSessionId: string | null
  setActiveSession: (id: string | null) => void
  setSessions: (sessions: Session[]) => void
  addSession: (session: Session) => void
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  activeSessionId: null,
  setActiveSession: (id) => set({ activeSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
  addSession: (session) => set((state) => ({ sessions: [session, ...state.sessions] })),
}))
