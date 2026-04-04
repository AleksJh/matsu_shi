import { apiClient } from './client'
import type { Session } from '../types'

export async function listAvailableModels(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>('/api/v1/chat/models')
  return data
}

export async function createSession(machine_model: string): Promise<Session> {
  const { data } = await apiClient.post<Session>('/api/v1/chat/sessions', { machine_model })
  return data
}

export async function listSessions(): Promise<Session[]> {
  const { data } = await apiClient.get<Session[]>('/api/v1/chat/sessions')
  return data
}

export async function deleteSession(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/chat/sessions/${id}`)
}

export async function renameSession(id: string, title: string): Promise<void> {
  await apiClient.patch(`/api/v1/chat/sessions/${id}/title`, { title })
}
