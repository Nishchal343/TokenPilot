import { useEffect, useState } from 'react'
import { CheckCircle, ChevronDown, Clock, Lock, Shield, User, XCircle } from 'lucide-react'
import { securityApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import PasswordChangeForm from '../components/PasswordChangeForm'

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}

const EVENT_LABELS = {
  login: '🔑 Login',
  logout: '🚪 Logout',
  password_change: '🔐 Password Changed',
  profile_update: '👤 Profile Updated',
}

export default function Security() {
  const { showToast } = useToast()
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [activityExpanded, setActivityExpanded] = useState(false)

  useEffect(() => {
    securityApi.info()
      .then(r => setInfo(r.data))
      .catch(() => showToast('error', 'Failed to load security info.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading/>

  return (
    <div className="security-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ACCOUNT</div>
          <h1>Security</h1>
          <p className="muted">Review your account security status and session activity.</p>
        </div>
      </div>

      <div className="security-layout">
        <div className={`security-password${passwordOpen ? ' is-open' : ''}`}>
          <button type="button" className="panel security-password-toggle" onClick={() => setPasswordOpen(open => !open)} aria-expanded={passwordOpen}>
            <span><span className="muted">Password security</span><strong>Change Password</strong><small>Update your account password securely.</small></span>
            <span className="security-password-icon"><Lock size={18}/><ChevronDown className="security-password-chevron" size={16}/></span>
          </button>
          <div className="security-password-content"><PasswordChangeForm showHeader={false}/></div>
        </div>

        {/* Account info card */}
        <div className="panel security-account-overview">
          <h3>Account Overview</h3>
          <div className="security-grid">
            <SecRow icon={<User size={16}/>} label="Email" value={info.email}/>
            <SecRow
              icon={info.is_verified ? <CheckCircle size={16} className="positive"/> : <XCircle size={16} className="negative"/>}
              label="Email Verified"
              value={info.is_verified ? 'Verified' : 'Not Verified'}
              highlight={info.is_verified ? 'positive' : 'negative'}
            />
            <SecRow icon={<Shield size={16}/>} label="Current Role" value={info.role}/>
            <SecRow icon={<Clock size={16}/>} label="Account Created" value={fmtDate(info.created_at)}/>
            <SecRow icon={<Clock size={16}/>} label="Last Login" value={fmtDate(info.last_login_at)}/>
          </div>
        </div>

        {/* Login history card */}
        <div className="panel">
          <h3>Recent Activity</h3>
          {info.recent_logins.length === 0 ? (
            <p className="muted">No recent activity recorded.</p>
          ) : (
            <div className="login-history">
              {info.recent_logins.slice(0, activityExpanded ? 10 : 3).map((log, i) => (
                <div key={i} className="login-row">
                  <span className="login-event">{EVENT_LABELS[log.event_type] || log.event_type}</span>
                  <span className="muted">{log.ip_address || '—'}</span>
                  <span className="muted">{fmtDate(log.created_at)}</span>
                </div>
              ))}
              {info.recent_logins.length > 3 && <button type="button" className="button secondary security-activity-toggle" onClick={() => setActivityExpanded(expanded => !expanded)}>
                {activityExpanded ? 'Show Less' : 'View More'}
              </button>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function SecRow({ icon, label, value, highlight }) {
  return (
    <div className="sec-row">
      <div className="sec-row-label"><span className="sec-icon">{icon}</span>{label}</div>
      <div className={`sec-row-value${highlight ? ` ${highlight}` : ''}`}>{value}</div>
    </div>
  )
}
