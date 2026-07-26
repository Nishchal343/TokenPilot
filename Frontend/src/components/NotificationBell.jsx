import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, Check, CheckCheck, CircleAlert, DollarSign, KeyRound, LockKeyhole, Megaphone, Sparkles, TrendingUp, User, UserPlus } from 'lucide-react'
import { notificationApi } from '../services/api'

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

function relativeTime(value) {
  const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`
  if (seconds < 172800) return 'Yesterday'
  return `${Math.floor(seconds / 86400)} days ago`
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const notificationRef = useRef(null)

  const load = () => notificationApi.list({ limit: 100 }).then(r => setItems(r.data)).catch(() => {})

  useEffect(() => {
    load()
    const refresh = () => load()
    const interval = window.setInterval(load, 30000)
    window.addEventListener('tokenpilot:notifications-updated', refresh)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('tokenpilot:notifications-updated', refresh)
    }
  }, [])

  useEffect(() => {
    if (!open) return undefined

    const closeOnOutsidePointer = event => {
      if (!notificationRef.current?.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = event => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', closeOnOutsidePointer, true)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePointer, true)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

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
    } catch { load() }
  }

  const openNotification = item => {
    setOpen(false)
    navigate('/notifications', { state: { notificationId: item.id } })
    if (!item.is_read) markRead(item.id)
  }

  const unread = items.filter(item => !item.is_read).length

  return <div className="notification-wrap" ref={notificationRef}>
    <button className="icon-button" onClick={() => setOpen(value => !value)} aria-label="Notifications" aria-expanded={open}>
      <Bell size={18}/>{unread > 0 && <i>{unread > 9 ? '9+' : unread}</i>}
    </button>
    {open && <div className="notification-panel">
      <div className="panel-head">
        <strong>Notifications</strong>
        {unread > 0 && <button onClick={markAllRead}><CheckCheck size={15}/> Mark all read</button>}
      </div>
      {items.length ? items.slice(0, 8).map(item => {
        const meta = TYPE_META[item.type] || { icon: Bell, color: '#a5afc2' }
        const Icon = meta.icon
        return <button className={`notification${item.is_read ? '' : ' unread'}`} key={item.id} onClick={() => openNotification(item)}>
          <span className="notification-icon" style={{ color: meta.color }}><Icon size={16}/></span>
          <span className="notification-copy"><b>{item.title}</b><small>{item.message}</small><em>{relativeTime(item.created_at)} · {item.is_read ? 'Read' : 'Unread'}</em></span>
          {!item.is_read && <span className="notification-unread-dot"/>}
        </button>
      }) : <p className="muted pad">You’re all caught up.</p>}
    </div>}
  </div>
}
