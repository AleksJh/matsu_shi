import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore, isJwtExpired } from '../store/authStore'

export default function PrivateRoute() {
  const jwt = useAuthStore.getState().jwt

  if (!jwt || isJwtExpired(jwt)) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
