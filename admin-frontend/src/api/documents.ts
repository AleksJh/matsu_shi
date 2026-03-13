import apiClient from './client'

export interface DocumentItem {
  id: number
  display_name: string
  machine_model: string
  category: string | null
  page_count: number | null
  chunk_count: number | null
  status: string | null
  indexed_at: string | null
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const { data } = await apiClient.get<DocumentItem[]>('/api/v1/admin/documents')
  return data
}
