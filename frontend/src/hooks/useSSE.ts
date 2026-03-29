import { useAuthStore } from '../store/authStore'
import { useMessageStore } from '../store/messageStore'
import type { QueryResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

/**
 * useSSE — submits a query to POST /api/v1/chat/query via fetch + ReadableStream.
 *
 * The backend sends a single SSE event:
 *   data: {QueryResponse JSON}\n\n
 *
 * Flow:
 *  1. Add user message to store immediately
 *  2. Set loading state
 *  3. Open fetch stream, parse first data: line
 *  4. Build assistant message from QueryResponse
 *  5. Add to store, clear loading
 */
export function useSSE() {
  const addMessage = useMessageStore((s) => s.addMessage)
  const setLoading = useMessageStore((s) => s.setLoading)

  async function sendMessage(sessionId: string, queryText: string): Promise<void> {
    const trimmed = queryText.trim()
    if (!trimmed) return

    const userMsgId = `user-${Date.now()}`
    addMessage(sessionId, {
      id: userMsgId,
      role: 'user',
      content: trimmed,
      created_at: new Date().toISOString(),
    })

    setLoading(sessionId)

    try {
      const jwt = useAuthStore.getState().jwt
      const res = await fetch(`${API_BASE}/api/v1/chat/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
        },
        body: JSON.stringify({ session_id: Number(sessionId), query_text: trimmed }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let parsed: QueryResponse | null = null

      outer: while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data:')) {
            const json = line.slice(5).trim()
            if (json) {
              parsed = JSON.parse(json) as QueryResponse
              break outer
            }
          }
        }
      }

      if (parsed) {
        addMessage(sessionId, {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: parsed.answer,
          response: parsed,
          created_at: new Date().toISOString(),
        })
      }
    } catch (err) {
      console.error('[useSSE] error:', err)
      addMessage(sessionId, {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Не удалось получить ответ. Попробуйте ещё раз.',
        created_at: new Date().toISOString(),
      })
    } finally {
      setLoading(null)
    }
  }

  return { sendMessage }
}
