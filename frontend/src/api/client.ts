import axios from 'axios'
import { useAuthStore } from '../store/authStore'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})

apiClient.interceptors.request.use((config) => {
  const jwt = useAuthStore.getState().jwt
  if (jwt) config.headers.Authorization = `Bearer ${jwt}`
  return config
})
