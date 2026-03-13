import apiClient from './client'

export async function adminLogin(username: string, password: string): Promise<string> {
  const { data } = await apiClient.post<{ access_token: string; token_type: string }>(
    '/api/v1/auth/admin/login',
    { username, password }
  )
  return data.access_token
}
