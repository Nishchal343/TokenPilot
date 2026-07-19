import { Navigate, Outlet } from 'react-router-dom'
import { useAuth, roleHome } from '../contexts/AuthContext'
import Loading from './Loading'

export default function GuestRoute() {
  const { isAuthenticated, user, initialized } = useAuth()
  if (!initialized) return <Loading/>
  if (isAuthenticated) return <Navigate to={roleHome(user)} replace/>
  return <Outlet/>
}
