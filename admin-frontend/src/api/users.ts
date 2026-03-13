import apiClient from './client'

export interface UserItem {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  status: 'pending' | 'active' | 'denied' | 'banned'
  created_at: string
  query_count: number
}

export interface UsersResponse {
  items: UserItem[]
  total: number
  page: number
  limit: number
}

export async function listUsers(
  status?: string,
  page = 1,
  limit = 20,
): Promise<UsersResponse> {
  const params: Record<string, string | number> = { page, limit }
  if (status) params.status = status
  const { data } = await apiClient.get<UsersResponse>('/api/v1/admin/users', { params })
  return data
}

export async function updateUserStatus(id: number, status: string): Promise<UserItem> {
  const { data } = await apiClient.put<UserItem>(`/api/v1/admin/users/${id}/status`, { status })
  return data
}
