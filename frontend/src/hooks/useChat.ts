import { useSessionStore } from '../store/sessionStore'
import { useMessageStore } from '../store/messageStore'
import type { Message } from '../types'

interface UseChatResult {
  messages: Message[]
  isLoading: boolean
}

export function useChat(): UseChatResult {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const messages = useMessageStore((s) =>
    activeSessionId ? (s.messages[activeSessionId] ?? []) : [],
  )
  const isLoading = useMessageStore(
    (s) => s.loadingSessionId === activeSessionId && activeSessionId !== null,
  )
  return { messages, isLoading }
}
