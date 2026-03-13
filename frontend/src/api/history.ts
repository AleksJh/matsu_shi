import { apiClient } from './client'
import type { Message } from '../types'

interface QueryHistoryItem {
  id: number
  query_text: string
  response_text: string | null
  model_used: string | null
  retrieval_score: number | null
  query_class: string | null
  no_answer: boolean | null
  created_at: string | null
}

export async function getSessionHistory(sessionId: string): Promise<Message[]> {
  const { data } = await apiClient.get<QueryHistoryItem[]>(
    `/api/v1/chat/sessions/${sessionId}/history`,
  )

  const messages: Message[] = []
  for (const item of data) {
    const ts = item.created_at ?? new Date().toISOString()

    // User turn
    messages.push({
      id: `${item.id}-user`,
      role: 'user',
      content: item.query_text,
      query_id: null,
      response: null,
      created_at: ts,
    })

    // Assistant turn — only if a response was persisted
    if (item.response_text !== null) {
      messages.push({
        id: `${item.id}-assistant`,
        role: 'assistant',
        content: item.response_text,
        query_id: String(item.id),
        response: {
          answer: item.response_text,
          citations: [],
          model_used: item.model_used ?? 'lite',
          no_answer: item.no_answer ?? false,
          retrieval_score: item.retrieval_score ?? 0,
        },
        created_at: ts,
      })
    }
  }

  return messages
}
