import { create } from 'zustand'
import type { Message } from '../types'

interface MessageState {
  messages: Record<string, Message[]>
  loadingSessionId: string | null
  addMessage: (sessionId: string, message: Message) => void
  setMessages: (sessionId: string, messages: Message[]) => void
  setLoading: (sessionId: string | null) => void
}

export const useMessageStore = create<MessageState>((set) => ({
  messages: {},
  loadingSessionId: null,
  addMessage: (sessionId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [sessionId]: [...(state.messages[sessionId] ?? []), message],
      },
    })),
  setMessages: (sessionId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [sessionId]: messages },
    })),
  setLoading: (sessionId) => set({ loadingSessionId: sessionId }),
}))
