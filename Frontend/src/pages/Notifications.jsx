import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, Check, CheckCheck, CircleAlert, DollarSign, KeyRound, LockKeyhole, Megaphone, Sparkles, TrendingUp, User, UserPlus } from 'lucide-react'
import { notificationApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'

const TYPE_META = {
  invitation_received: { icon: UserPlus, color: '#a99bff' },
  invitation_accepted: { icon: Check, color: '#35d49a' },
  invitation_sent: { icon: UserPlus, color: '#a99bff' },
  team_member_joined: { icon: User, color: '#60a5fa' },
  invitation_rejected: { icon: CircleAlert, color: '#ff7a95' },
  budget_approved: { icon: DollarSign, color: '#35d49a' },
  budget_updated: { icon: DollarSign, color: '#fbbf24' },
  budget_exceeded: { icon: AlertTriangle, color: '#ff9e5e' },
  token_optimization: { icon: Sparkles, color: '#c4b5fd' },
  token_limit_changed: { icon: TrendingUp, color: '#60a5fa' },
  usage_spike: { icon: TrendingUp, color: '#ff9e5e' },
  api_key_request: { icon: Bell, color: '#60a5fa' },
  api_key_approved: { icon: Check, color: '#35d49a' },
  promotion: { icon: User, color: '#c4b5fd' },
  demotion: { icon: User, color: '#fbbf24' },
  reporting_manager_changed: { icon: User, color: '#60a5fa' },
  security_alert: { icon: LockKeyhole, color: '#ff7a95' },
  password_changed: { icon: KeyRound, color: '#35d49a' },
  profile_updated: { icon: User, color: '#60a5fa' },
  system: { icon: Megaphone, color: '#a99bff' },
}

function formatDate(value) {
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

function groupFor(value) {
  const date = new Date(value)
  const today = new Date()
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const startDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const days = Math.floor((startToday - startDate) / 86400000)
  return days === 0 ? 'Today' : days === 1 ? 'Yesterday' : 'Earlier'
}

function resourcePath(type, user) {
  const company = user?.type === 'company'
  const manager = user?.role === 'manager'
  if (type?.startsWith('invitation_') || type === 'team_member_joined') return '/invitations'
  if (type?.startsWith('api_key_') || type?.startsWith('budget_')) {
    return company ? '/dashboard/company/budget-approval' : manager ? '/dashboard/team-leader/team-budget' : '/dashboard/member/requests'
  }
  return null
}

export default function Notifications() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { showToast } = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const highlightedId = location.state?.notificationId
  const handledHighlight = useRef(null)

  const load = async () => {
    try {
      const response = await notificationApi.list({ limit: 100 })
      setItems(response.data)
    } catch { showToast('error', 'Failed to load notifications.') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const refresh = () => load()
    window.addEventListener('tokenpilot:notifications-updated', refresh)
    return () => window.removeEventListener('tokenpilot:notifications-updated', refresh)
  }, [])

  useEffect(() => {
    if (!highlightedId || loading || handledHighlight.current === highlightedId) return
    const target = document.querySelector(`[data-notification-id="${highlightedId}"]`)
    if (!target) return
    handledHighlight.current = highlightedId
    const selected = items.find(item => String(item.id) === String(highlightedId))
    if (selected && !selected.is_read) markRead(selected.id)
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    target.classList.add('notification-focused')
    const timer = window.setTimeout(() => target.classList.remove('notification-focused'), 2800)
    return () => window.clearTimeout(timer)
  }, [highlightedId, items, loading])

  const markRead = async (id) => {
    setItems(current => current.map(item => item.id === id ? { ...item, is_read: true } : item))
    try {
      await notificationApi.read(id)
      window.dispatchEvent(new Event('tokenpilot:notifications-updated'))
    } catch { load() }
  }

  const markAllRead = async () => {
    setItems(current => current.map(item => ({ ...item, is_read: true })))
    try {
      await notificationApi.readAll()
      window.dispatchEvent(new Event('tokenpilot:notifications-updated'))
      showToast('success', 'All notifications marked as read.')
    } catch { load() }
  }

  const openDetails = (item, path) => {
    if (!item.is_read) markRead(item.id)
    navigate(path)
  }

  if (loading) return <Loading/>

  const unread = items.filter(item => !item.is_read).length
  const groups = ['Today', 'Yesterday', 'Earlier'].map(label => ({ label, items: items.filter(item => groupFor(item.created_at) === label) })).filter(group => group.items.length)

  return <div className="notifications-page">
    <div className="page-heading">
      <div><div className="eyebrow">INBOX</div><h1>Notifications {unread > 0 && <span className="notif-badge">{unread > 99 ? '99+' : unread}</span>}</h1><p className="muted">Stay updated on your workspace activity.</p></div>
      {unread > 0 && <button className="button secondary" onClick={markAllRead}><CheckCheck size={15}/> Mark all read</button>}
    </div>

    {groups.length ? <div className="notification-groups">{groups.map(group => <section key={group.label} className="notification-group">
      <h2>{group.label}</h2>
      <div className="notif-list">{group.items.map(item => {
        const meta = TYPE_META[item.type] || { icon: Bell, color: '#a5afc2' }
        const Icon = meta.icon
        const detailsPath = resourcePath(item.type, user)
        return <article key={item.id} data-notification-id={item.id} className={`notif-item panel${item.is_read ? '' : ' unread-item'}`}>
          <div className="notif-icon-wrap" style={{ color: meta.color }}><Icon size={20}/>{!item.is_read && <span className="notif-dot"/>}</div>
          <div className="notif-content"><div className="notif-title">{item.title}</div><div className="notif-message muted">{item.message}</div><div className="notif-time muted">{formatDate(item.created_at)}</div></div>
          <div className="notif-actions">{detailsPath && <button className="button secondary" onClick={() => openDetails(item, detailsPath)}>View Details</button>}{item.is_read ? <span className="notification-status read"><Check size={13}/> Read</span> : <button className="button secondary" onClick={() => markRead(item.id)}>Mark as Read</button>}</div>
        </article>
      })}</div>
    </section>)}</div> : <div className="empty-state page-empty"><div className="empty-icon"><Bell size={32}/></div><h2>No notifications available.</h2><p>When workspace activity happens, you'll see it here.</p></div>}
  </div>
}
