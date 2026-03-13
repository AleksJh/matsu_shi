import { apiClient } from './client'

export async function submitFeedback(queryId: string, rating: 1 | -1): Promise<void> {
  await apiClient.post(`/api/v1/feedback/${queryId}`, { rating })
}
