import apiClient from './client'

export interface StatsResponse {
  queries_today: number
  avg_retrieval_score_7d: number | null
  model_usage: Record<string, number>
  feedback_up: number
  feedback_down: number
  users: Record<string, number>
}

export async function getStats(): Promise<StatsResponse> {
  const { data } = await apiClient.get<StatsResponse>('/api/v1/admin/stats')
  return data
}
