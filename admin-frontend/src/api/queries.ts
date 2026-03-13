import apiClient from './client'

export interface QueryItem {
  id: number
  user_id: number | null
  session_id: number | null
  query_text: string
  response_text: string | null
  model_used: string | null
  retrieval_score: number | null
  query_class: string | null
  no_answer: boolean | null
  latency_ms: number | null
  created_at: string | null
}

export interface QueryDetail extends QueryItem {
  feedback_rating: number | null
}

export interface QueryFilters {
  user_id?: number
  since?: string
  model_used?: string
}

export async function listQueries(
  filters: QueryFilters,
  limit: number,
  offset: number,
): Promise<QueryItem[]> {
  const params: Record<string, string | number> = { limit, offset }
  if (filters.user_id !== undefined) params.user_id = filters.user_id
  if (filters.since) params.since = filters.since
  if (filters.model_used) params.model_used = filters.model_used
  const { data } = await apiClient.get<QueryItem[]>('/api/v1/admin/queries', { params })
  return data
}

export async function getQuery(id: number): Promise<QueryDetail> {
  const { data } = await apiClient.get<QueryDetail>(`/api/v1/admin/queries/${id}`)
  return data
}
