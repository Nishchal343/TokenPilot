import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { CheckCircle2, XCircle, AlertTriangle, Calendar, User, Shield, Info, ArrowRight } from 'lucide-react'
import { invitationApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import Logo from '../components/Logo'

export default function InvitationAccept() {
  const { token } = useParams()
  const nav = useNavigate()
  const { showToast } = useToast()

  const [loading, setLoading] = useState(true)
  const [inviteData, setInviteData] = useState(null)
  const [error, setError] = useState(null)
  
  // Status states
  const [accepted, setAccepted] = useState(false)
  const [rejected, setRejected] = useState(false)
  const [expired, setExpired] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const verifyToken = async () => {
    setLoading(true)
    setError(null)
    setExpired(false)
    try {
      const response = await invitationApi.verify(token)
      setInviteData(response.data)
    } catch (err) {
      console.error(err)
      if (err.response?.status === 410 || err.response?.data?.detail?.includes('expired')) {
        setExpired(true)
      } else {
        setError(err.response?.data?.detail || 'Invalid or expired invitation token.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      verifyToken()
    }
  }, [token])

  const handleAccept = async () => {
    if (!inviteData) return
    setSubmitting(true)
    try {
      if (inviteData.account_exists) {
        // Employee has an account already, link and log them in
        await invitationApi.accept({ token })
        showToast('success', 'Invitation accepted! Please sign in to access your workspace.')
        setAccepted(true)
        setTimeout(() => {
          nav(`/login?kind=employee&email=${inviteData.email}`)
        }, 2000)
      } else {
        // No account exists, redirect to complete signup
        showToast('success', 'Invitation validated. Let\'s create your account.')
        setTimeout(() => {
          nav(`/register?kind=employee&token=${token}&email=${inviteData.email}`)
        }, 1200)
      }
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to accept invitation.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    setSubmitting(true)
    try {
      await invitationApi.reject({ token })
      showToast('success', 'Invitation declined.')
      setRejected(true)
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to decline invitation.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Loading />

  // Expired View
  if (expired) {
    return (
      <div className="auth-page" style={{ gridTemplateColumns: '1fr', display: 'grid', placeItems: 'center' }}>
        <div className="auth-form" style={{ textAlign: 'center' }}>
          <Logo />
          <div className="auth-heading" style={{ marginTop: '24px' }}>
            <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(255, 89, 120, 0.1)', borderRadius: '50%', color: '#ff5978', marginBottom: '16px' }}>
              <AlertTriangle size={32} />
            </div>
            <h2>Invitation Expired</h2>
            <p className="muted" style={{ margin: '12px 0 24px', fontSize: '14px', lineHeight: '1.6' }}>
              This invitation token has expired. For security, invitations are valid for 7 days only.
            </p>
            <div style={{ padding: '16px', background: '#141925', border: '1px solid #20283a', borderRadius: '12px', textAlign: 'left', marginBottom: '24px' }}>
              <span className="muted" style={{ fontSize: '11px', display: 'block', textTransform: 'uppercase' }}>What should I do?</span>
              <p className="muted" style={{ fontSize: '12px', margin: '6px 0 0', lineHeight: '1.5' }}>
                Please get in touch with the company administrator or team manager who invited you and request a new invitation.
              </p>
            </div>
            <a href="mailto:support@tokenpilot.com" className="button secondary full">
              Contact Company Support
            </a>
          </div>
        </div>
      </div>
    )
  }

  // Error/Invalid Token View
  if (error) {
    return (
      <div className="auth-page" style={{ gridTemplateColumns: '1fr', display: 'grid', placeItems: 'center' }}>
        <div className="auth-form" style={{ textAlign: 'center' }}>
          <Logo />
          <div className="auth-heading" style={{ marginTop: '24px' }}>
            <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(255, 89, 120, 0.1)', borderRadius: '50%', color: '#ff5978', marginBottom: '16px' }}>
              <XCircle size={32} />
            </div>
            <h2>Invitation Unavailable</h2>
            <p className="muted" style={{ margin: '12px 0 24px', fontSize: '14px', lineHeight: '1.6' }}>
              {error}
            </p>
            <button className="button secondary full" onClick={() => nav('/')}>
              Back to Home
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Accepted Confirmation View
  if (accepted) {
    return (
      <div className="auth-page" style={{ gridTemplateColumns: '1fr', display: 'grid', placeItems: 'center' }}>
        <div className="auth-form" style={{ textAlign: 'center' }}>
          <Logo />
          <div className="auth-heading" style={{ marginTop: '24px' }}>
            <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(53, 212, 154, 0.1)', borderRadius: '50%', color: '#35d49a', marginBottom: '16px' }}>
              <CheckCircle2 size={32} />
            </div>
            <h2>Invitation Accepted!</h2>
            <p className="muted" style={{ margin: '12px 0 24px', fontSize: '14px', lineHeight: '1.6' }}>
              Redirecting you to the sign-in page to access your workspace.
            </p>
            <button className="button primary full" onClick={() => nav('/login')}>
              Go to Login Now <ArrowRight size={15}/>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Rejected Confirmation View
  if (rejected) {
    return (
      <div className="auth-page" style={{ gridTemplateColumns: '1fr', display: 'grid', placeItems: 'center' }}>
        <div className="auth-form" style={{ textAlign: 'center' }}>
          <Logo />
          <div className="auth-heading" style={{ marginTop: '24px' }}>
            <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(139, 149, 170, 0.1)', borderRadius: '50%', color: '#8b95aa', marginBottom: '16px' }}>
              <Info size={32} />
            </div>
            <h2>Invitation Declined</h2>
            <p className="muted" style={{ margin: '12px 0 24px', fontSize: '14px', lineHeight: '1.6' }}>
              You have declined the invitation to join this organization. The administrator has been notified.
            </p>
            <button className="button secondary full" onClick={() => nav('/')}>
              Back to Home
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Active Acceptance View
  const expiryDate = inviteData?.expires_at ? new Date(inviteData.expires_at).toLocaleDateString(undefined, { dateStyle: 'long', timeStyle: 'short' }) : ''
  const initial = inviteData?.company_name ? inviteData.company_name[0].toUpperCase() : 'W'

  return (
    <div className="auth-page" style={{ gridTemplateColumns: '1fr', display: 'grid', placeItems: 'center' }}>
      <div className="auth-form" style={{ width: 'min(450px, 100%)' }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <Logo />
        </div>
        
        <div className="panel" style={{ padding: '28px', background: 'linear-gradient(145deg, #141925, #11141d)', border: '1px solid #20283a', borderRadius: '16px' }}>
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div className="avatar large" style={{ margin: '0 auto 12px', width: '56px', height: '56px', fontSize: '20px', background: 'linear-gradient(135deg, #8b5cf6, #4f46e5)' }}>
              {initial}
            </div>
            <h2 style={{ fontSize: '22px', color: '#eef0f7', margin: '0 0 6px' }}>Workspace Invitation</h2>
            <p className="muted" style={{ fontSize: '13px', margin: 0 }}>
              You have been invited to join <strong style={{ color: '#c4b5fd' }}>{inviteData?.company_name}</strong>
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '28px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', background: '#0b0d13', padding: '12px 16px', borderRadius: '10px', border: '1px solid #20283a' }}>
              <User size={16} className="muted"/>
              <div>
                <span className="muted" style={{ fontSize: '10px', display: 'block', textTransform: 'uppercase' }}>Invited Email</span>
                <span style={{ fontSize: '13px', color: '#e2e8f0', fontWeight: '500' }}>{inviteData?.email}</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', background: '#0b0d13', padding: '12px 16px', borderRadius: '10px', border: '1px solid #20283a' }}>
              <Shield size={16} className="muted"/>
              <div>
                <span className="muted" style={{ fontSize: '10px', display: 'block', textTransform: 'uppercase' }}>Offered Role</span>
                <span style={{ fontSize: '13px', color: '#e2e8f0', fontWeight: '500' }}>
                  {inviteData?.role_offered === 'manager' ? 'Team Lead (Manager)' : 'Employee'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', background: '#0b0d13', padding: '12px 16px', borderRadius: '10px', border: '1px solid #20283a' }}>
              <Calendar size={16} className="muted"/>
              <div>
                <span className="muted" style={{ fontSize: '10px', display: 'block', textTransform: 'uppercase' }}>Valid Until</span>
                <span style={{ fontSize: '13px', color: '#ffbd79', fontWeight: '500' }}>{expiryDate}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button 
              className="button primary full" 
              onClick={handleAccept} 
              disabled={submitting}
              style={{ padding: '12px 0' }}
            >
              {submitting ? 'Processing...' : inviteData?.account_exists ? 'Accept & Login' : 'Accept & Register'}
            </button>
            <button 
              className="button secondary full" 
              onClick={handleReject} 
              disabled={submitting}
              style={{ padding: '11px 0' }}
            >
              Decline Invitation
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
