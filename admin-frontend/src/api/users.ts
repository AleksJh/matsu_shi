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

export async function listUsers(
  status?: string,
  page = 1,
  limit = 20,
): Promise<UserItem[]> {
  const params: Record<string, string | number> = { limit, offset: (page - 1) * limit }
  if (status) params.status = status
  const { data } = await apiClient.get<UserItem[]>('/api/v1/admin/users', { params })
  return data
}

export async function updateUserStatus(id: number, status: string): Promise<UserItem> {
  const { data } = await apiClient.put<UserItem>(`/api/v1/admin/users/${id}/status`, { status })
  return data
}

export async function deleteUser(id: number): Promise<void> {
  await apiClient.delete(`/api/v1/admin/users/${id}`)
}

export async function deleteUsersBulk(ids: number[]): Promise<{ deleted: number }> {
  const { data } = await apiClient.post<{ deleted: number }>('/api/v1/admin/users/bulk-delete', { ids })
  return data
}

export async function sendUserMessage(id: number, message: string): Promise<void> {
  await apiClient.post(`/api/v1/admin/users/${id}/message`, { message })
}
