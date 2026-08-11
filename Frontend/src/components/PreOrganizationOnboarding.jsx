import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bell, BookOpen, Check, Circle, Clock3, FileText, HelpCircle, Mail, RefreshCw, User, Users, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { invitationApi, notificationApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

export default function PreOrganizationOnboarding({ variant = 'dashboard' }) {
  const { profile, refreshOrganization } = useAuth()
  const [invitations, setInvitations] = useState([])
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const [invitationResult, notificationResult] = await Promise.allSettled([
      invitationApi.mine(),
      notificationApi.list(),
    ])
    if (invitationResult.status === 'fulfilled') setInvitations(invitationResult.value.data || [])
    if (notificationResult.status === 'fulfilled') setNotifications(notificationResult.value.data || [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const pending = useMemo(() => invitations.filter(item => item.status === 'pending'), [invitations])
  const accepted = useMemo(() => invitations.filter(item => item.status === 'accepted'), [invitations])

  const action = async (invitation, type) => {
    setWorkingId(invitation.id)
    try {
      if (type === 'accept') {
        await invitationApi.accept({ token: invitation.token })
        await refreshOrganization()
      } else {
        await invitationApi.reject({ token: invitation.token })
        await load()
      }
    } catch {
      // Onboarding stays usable even when an invitation changes elsewhere.
      await load()
    } finally {
      setWorkingId(null)
    }
  }

  if (variant === 'organization') {
    return <OnboardingShell title="No Organization Yet" eyebrow="MY ORGANIZATION">
      <p className="onboarding-copy">You are currently not a member of any organization. When you accept an invitation, your workspace, team members and permissions will appear here.</p>
      <StatusSummary pending={pending.length} accepted={accepted.length} />
      <InvitationList invitations={pending} loading={loading} workingId={workingId} onAction={action} />
      <QuickActions onRefresh={load} />
    </OnboardingShell>
  }

  if (variant === 'budget') {
    return <OnboardingShell title="No Budget Available" eyebrow="MY BUDGET">
      <p className="onboarding-copy">Budgets are managed by organizations. Once you join an organization, your allocated budget, token usage and AI spend will appear here.</p>
      <div className="stats-grid onboarding-preview">
        <Preview label="Organization Budget" />
        <Preview label="Your Budget" />
        <Preview label="Remaining Tokens" />
        <Preview label="Monthly Usage" />
      </div>
      <div className="onboarding-status"><Clock3 size={16} /> Waiting for Organization</div>
      <InvitationList invitations={pending} loading={loading} workingId={workingId} onAction={action} />
    </OnboardingShell>
  }

  return <div className="dashboard onboarding-dashboard">
    <div className="page-heading"><div><div className="eyebrow">EMPLOYEE ONBOARDING</div><h1>Welcome to TokenPilot 👋</h1><p className="muted">Your account is active. You’re currently not part of an organization.</p></div></div>
    <section className="panel onboarding-welcome"><div><h2>Your workspace is ready when you are.</h2><p>Once you receive and accept an invitation, you’ll unlock your organization’s AI Workspace, analytics and budgets.</p></div><Users size={42} /></section>
    <div className="dashboard-grid">
      <section className="panel"><div className="panel-head"><h3>Account Status</h3><Check size={17} className="positive" /></div><StatusLine icon={<Check size={15} />} text="Email Verified" done /><StatusLine icon={<Check size={15} />} text="Account Active" done /><StatusLine icon={<Circle size={15} />} text="Waiting for Organization" /></section>
      <section className="panel"><div className="panel-head"><h3>Pending Invitations</h3><Mail size={17} className="muted" /></div><InvitationList invitations={pending} loading={loading} workingId={workingId} onAction={action} /></section>
    </div>
    <div className="dashboard-grid lower"><section className="panel"><div className="panel-head"><h3>Recent Notifications</h3><Bell size={17} className="muted" /></div>{notifications.length ? notifications.slice(0, 5).map(item => <div className="list-row" key={item.id}><span className="notification-dot" /><span><b>{item.title}</b><small>{item.message}</small></span></div>) : <div className="empty-inline"><Bell size={18} /> No recent notifications.</div>}</section><section className="panel"><div className="panel-head"><h3>Activity Timeline</h3><Clock3 size={17} className="muted" /></div><StatusLine icon={<Check size={15} />} text="Account Active" done /><StatusLine icon={<Check size={15} />} text="Email Verified" done /><StatusLine icon={pending.length ? <Mail size={15} /> : <Circle size={15} />} text={pending.length ? 'Invitation Received' : 'Waiting for Organization Invitation'} /></section></div>
    <QuickActions onRefresh={load} />
    <section><div className="eyebrow">GETTING STARTED</div><div className="feature-grid onboarding-links"><Link className="feature-card" to="/docs"><BookOpen size={20} /><h3>How Invitations Work</h3><p>Learn how your organization workspace becomes available.</p></Link><Link className="feature-card" to="/docs"><FileText size={20} /><h3>Documentation</h3><p>Explore TokenPilot features and workflows.</p></Link><Link className="feature-card" to="/help"><HelpCircle size={20} /><h3>Help Center</h3><p>Find answers or contact support when you need help.</p></Link></div></section>
  </div>
}

function OnboardingShell({ eyebrow, title, children }) {
  return <div className="dashboard"><div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1></div></div>{children}</div>
}

function StatusSummary({ pending, accepted }) {
  return <div className="stats-grid onboarding-summary"><Preview label="Pending Invitations" value={pending} /><Preview label="Accepted Invitations" value={accepted} /><Preview label="Organization Status" value="Waiting" /></div>
}

function Preview({ label, value = '—' }) {
  return <div className="stat-card"><div><span className="muted">{label}</span><strong>{value}</strong></div></div>
}

function StatusLine({ icon, text, done }) {
  return <div className="onboarding-status"><span className={done ? 'positive' : 'muted'}>{icon}</span><span>{text}</span></div>
}

function InvitationList({ invitations, loading, workingId, onAction }) {
  if (loading) return <div className="empty-inline"><RefreshCw size={17} /> Checking for invitations…</div>
  if (!invitations.length) return <div className="empty-inline"><Mail size={18} /> No pending invitations.</div>
  return <div className="onboarding-invitations">{invitations.map(invitation => <div className="list-row" key={invitation.id}><span className="avatar small">{invitation.company_name?.[0]}</span><span><b>{invitation.company_name}</b><small>Invited by {invitation.invited_by_name} · {invitation.role_offered}</small></span><span className="invitation-actions"><button className="button primary" onClick={() => onAction(invitation, 'accept')} disabled={workingId === invitation.id}><Check size={14} /> Accept</button><button className="button secondary" onClick={() => onAction(invitation, 'decline')} disabled={workingId === invitation.id}><X size={14} /> Decline</button></span></div>)}</div>
}

function QuickActions({ onRefresh }) {
  return <div className="onboarding-quick-actions"><button className="button secondary" onClick={onRefresh}><RefreshCw size={15} /> Refresh Invitations</button><Link className="button secondary" to="/profile"><User size={15} /> Edit Profile</Link><Link className="button secondary" to="/notifications"><Bell size={15} /> Notification Center</Link></div>
}
