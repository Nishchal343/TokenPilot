import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, BookOpen, Bug, HelpCircle, LogOut, Settings, Shield, User } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import BugReportModal from './BugReportModal'

export default function ProfileDropdown() {
  const { profile, user, logout } = useAuth()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [bugModal, setBugModal] = useState(false)
  const ref = useRef()

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const initial = (profile?.name || user?.name || 'U')[0].toUpperCase()

  const go = (path) => { setOpen(false); nav(path) }

  const handleLogout = () => { setOpen(false); logout() }

  const links = [
    { icon: <User size={15}/>, label: 'Profile', path: '/profile' },
    { icon: <Settings size={15}/>, label: 'Settings', path: '/settings' },
    { icon: <Bell size={15}/>, label: 'Notifications', path: '/notifications' },
    { icon: <Shield size={15}/>, label: 'Security', path: '/security' },
  ]

  const supportLinks = [
    { icon: <HelpCircle size={15}/>, label: 'Help Center', path: '/help' },
    { icon: <BookOpen size={15}/>, label: 'Documentation', path: '/docs' },
    { icon: <Bug size={15}/>, label: 'Report a Bug', action: () => { setOpen(false); setBugModal(true) } },
  ]

  const API_BASE = import.meta.env.VITE_API_URL || ''
  const avatarSrc = profile?.avatar_url ? `${API_BASE}${profile.avatar_url}` : null

  return (
    <div className="profile-dropdown-wrap" ref={ref}>
      <button
        className="avatar clickable"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        title={profile?.name || 'Account'}
      >
        {avatarSrc ? <img src={avatarSrc} alt="avatar" className="avatar-img-preview" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}/> : initial}
      </button>

      {open && (
        <div className="profile-dropdown" role="menu">
          {/* Header */}
          <div className="pd-header">
            {avatarSrc ? <img src={avatarSrc} alt="avatar" className="avatar-img-preview" style={{ width: '48px', height: '48px', borderRadius: '50%', objectFit: 'cover' }}/> : <div className="avatar large">{initial}</div>}
            <div className="pd-user-info">
              <span className="pd-name">{profile?.name || 'User'}</span>
              <span className="pd-email muted">{profile?.email || '—'}</span>
              <span className="pd-role-badge">{profile?.role || '—'}</span>
            </div>
          </div>

          <div className="pd-divider"/>

          {/* Workspace section */}
          <div className="pd-section-label">Workspace</div>
          <div className="pd-workspace">
            <span className="pd-workspace-name">{profile?.companyName || 'My Company'}</span>
            <span className="muted">{profile?.role}</span>
          </div>

          <div className="pd-divider"/>

          {/* Account links */}
          <div className="pd-section-label">Account</div>
          {links.map(({ icon, label, path }) => (
            <button key={label} className="pd-item" role="menuitem" onClick={() => go(path)}>
              <span className="pd-item-icon">{icon}</span>
              {label}
            </button>
          ))}

          <div className="pd-divider"/>

          {/* Support links */}
          <div className="pd-section-label">Support</div>
          {supportLinks.map(({ icon, label, path, action }) => (
            <button key={label} className="pd-item" role="menuitem" onClick={action || (() => go(path))}>
              <span className="pd-item-icon">{icon}</span>
              {label}
            </button>
          ))}

          <div className="pd-divider"/>

          {/* Logout */}
          <button className="pd-item pd-logout" role="menuitem" onClick={handleLogout}>
            <span className="pd-item-icon"><LogOut size={15}/></span>
            Logout
          </button>
        </div>
      )}

      {bugModal && <BugReportModal onClose={() => setBugModal(false)}/>}
    </div>
  )
}
