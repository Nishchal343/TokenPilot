import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi, api } from '../services/api'
import { useToast } from './ToastContext'

const AuthContext = createContext(null)
const decode = token => { try { return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) } catch { return null } }
export function AuthProvider({ children }) {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [initialized, setInitialized] = useState(false)
  const { showToast } = useToast()
  const nav = useNavigate()

  const fetchProfile = useCallback(async (tokenType) => {
    try {
      const r = await api.get('/profile')
      setProfile({
        name: r.data.name,
        email: r.data.email,
        role: r.data.role,
        companyName: r.data.company_name || 'Workspace',
        avatar_url: r.data.avatar_url
      })
    } catch (err) {
      console.error('Failed to fetch profile', err)
    }
  }, [])

  const login = (response, email) => {
    const t = response.data.access_token
    localStorage.setItem('tokenpilot_token', t)
    if (email) {
      localStorage.setItem('tokenpilot_email', email)
    }
    const decoded = decode(t)
    localStorage.setItem('tokenpilot_user', JSON.stringify(decoded))
    setToken(t)
    setUser(decoded)
    fetchProfile(decoded.type)
    if (decoded?.type === 'employee' && !decoded.company_id) {
      showToast('info', "You're not part of any organization yet.")
    }
  }

  const logout = useCallback((reason) => {
    localStorage.removeItem('tokenpilot_token')
    localStorage.removeItem('tokenpilot_user')
    localStorage.removeItem('tokenpilot_email')
    setToken(null)
    setUser(null)
    setProfile(null)
    nav('/login', { replace: true })
    if (reason === 'session_expired') {
      showToast('error', 'Your session has expired. Please log in again.')
    }
  }, [nav, showToast])

  const refreshOrganization = useCallback(async () => {
    const response = await api.get('/organization/me')
    const organizationId = response.data.company?.id || null
    setUser(previous => {
      if (!previous) return previous
      const next = {
        ...previous,
        company_id: organizationId,
        role: response.data.current_employee?.role || previous.role || 'employee',
      }
      localStorage.setItem('tokenpilot_user', JSON.stringify(next))
      return next
    })
    return organizationId
  }, [])

  useEffect(() => {
    const t = localStorage.getItem('tokenpilot_token')
    const u = localStorage.getItem('tokenpilot_user')
    if (t) {
      setToken(t)
      let decoded = null
      if (u) {
        try {
          decoded = JSON.parse(u)
          setUser(decoded)
        } catch {
          decoded = decode(t)
          setUser(decoded)
        }
      } else {
        decoded = decode(t)
        setUser(decoded)
      }
      if (decoded) {
        fetchProfile(decoded.type)
      }
    }
    setInitialized(true)
  }, [fetchProfile])

  useEffect(() => {
    const fn = () => logout('session_expired')
    window.addEventListener('tokenpilot:logout', fn)
    return () => window.removeEventListener('tokenpilot:logout', fn)
  }, [logout])

  return <AuthContext.Provider value={{ token, user, profile, isAuthenticated: !!user, initialized, login, logout, fetchProfile, refreshOrganization, authApi }}>{children}</AuthContext.Provider>
}
export const useAuth = () => useContext(AuthContext)
export const roleHome = user => user?.type === 'company' ? '/dashboard/company' : user?.role === 'manager' ? '/dashboard/team-leader' : '/dashboard/member'
