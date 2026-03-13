import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const apiClient = axios.create({
  baseURL: '/',
})

apiClient.interceptors.request.use((config) => {
  const jwt = useAuthStore.getState().jwt
  if (jwt) {
    config.headers.Authorization = `Bearer ${jwt}`
  }
  return config
})

export default apiClient
