import { useEffect, useState } from 'react'
import { Bell, Check, CheckCheck, Trash2 } from 'lucide-react'
import { notificationApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'

const TYPE_ICONS = {
  invitation_accepted: '✅',
  invitation_rejected: '❌',
  invitation_sent: '📨',
  budget_updated: '💰',
  token_limit_changed: '🔢',
  password_changed: '🔐',
  profile_updated: '👤',
  system: 'ℹ️',
}

function timeAgo(dt) {
  const diff = (Date.now() - new Date(dt)) / 1000
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function Notifications() {
  const { showToast } = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const r = await notificationApi.list()
      setItems(r.data)
    } catch { showToast('error', 'Failed to load notifications.') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const markRead = async (id) => {
    try { await notificationApi.read(id); load() } catch {}
  }
  const markAllRead = async () => {
    try { await notificationApi.readAll(); load(); showToast('success', 'All notifications marked as read.') } catch {}
  }
  const deleteNotif = async (id) => {
    try { await notificationApi.delete(id); setItems(i => i.filter(n => n.id !== id)); showToast('success', 'Notification deleted.') } catch {}
  }

  if (loading) return <Loading/>

  const unread = items.filter(n => !n.is_read).length

  return (
    <div className="notifications-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">INBOX</div>
          <h1>Notifications {unread > 0 && <span className="notif-badge">{unread}</span>}</h1>
          <p className="muted">Stay updated on your workspace activity.</p>
        </div>
        {unread > 0 && (
          <button className="button secondary" onClick={markAllRead}>
            <CheckCheck size={15}/> Mark all read
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="empty-state page-empty">
          <div className="empty-icon"><Bell size={32}/></div>
          <h2>No notifications available.</h2>
          <p>When workspace activity happens, you'll see it here.</p>
        </div>
      ) : (
        <div className="notif-list">
          {items.map(n => (
            <div key={n.id} className={`notif-item panel ${n.is_read ? '' : 'unread-item'}`}>
              <div className="notif-icon-wrap">
                <span className="notif-emoji">{TYPE_ICONS[n.type] || '🔔'}</span>
                {!n.is_read && <span className="notif-dot"/>}
              </div>
              <div className="notif-content">
                <div className="notif-title">{n.title}</div>
                <div className="notif-message muted">{n.message}</div>
                <div className="notif-time muted">{timeAgo(n.created_at)}</div>
              </div>
              <div className="notif-actions">
                {!n.is_read && (
                  <button className="icon-button" title="Mark read" onClick={() => markRead(n.id)}>
                    <Check size={15}/>
                  </button>
                )}
                <button className="icon-button danger-icon" title="Delete" onClick={() => deleteNotif(n.id)}>
                  <Trash2 size={15}/>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
