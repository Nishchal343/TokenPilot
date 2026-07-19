import { useState } from 'react'
import { Lock, Eye, EyeOff, ShieldCheck, Key, X, RefreshCw } from 'lucide-react'
import { settingsApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'

export default function Settings() {
  const { showToast } = useToast()
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [loading, setLoading] = useState(false)
  const [show, setShow] = useState({ current: false, new: false, confirm: false })

  // OTP Modal State
  const [showOtpModal, setShowOtpModal] = useState(false)
  const [otp, setOtp] = useState('')
  const [otpLoading, setOtpLoading] = useState(false)
  const [resending, setResending] = useState(false)

  const set = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))
  const toggle = key => setShow(s => ({ ...s, [key]: !s[key] }))

  const strength = (pwd) => {
    if (!pwd) return null
    let score = 0
    if (pwd.length >= 8) score++
    if (/[A-Z]/.test(pwd)) score++
    if (/[0-9]/.test(pwd)) score++
    if (/[^A-Za-z0-9]/.test(pwd)) score++
    return score
  }
  const strengthLabel = s => ['', 'Weak', 'Fair', 'Good', 'Strong'][s] || ''
  const strengthClass = s => ['', 'weak', 'fair', 'good', 'strong'][s] || ''

  const handleRequestOtp = async (e) => {
    e.preventDefault()
    if (form.new_password !== form.confirm_password) {
      showToast('error', 'New password and confirmation do not match.')
      return
    }
    if (form.new_password.length < 8) {
      showToast('error', 'Password must be at least 8 characters.')
      return
    }
    setLoading(true)
    try {
      const r = await settingsApi.changePassword(form)
      showToast('success', r.data.message || 'Verification code sent to email.')
      setShowOtpModal(true)
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to request password change.')
    } finally { setLoading(false) }
  }

  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    if (!otp || otp.length !== 6) {
      showToast('error', 'Please enter a valid 6-digit verification code.')
      return
    }
    setOtpLoading(true)
    try {
      const r = await settingsApi.changePasswordVerify({
        otp,
        new_password: form.new_password,
        confirm_password: form.confirm_password
      })
      showToast('success', r.data.message || 'Password updated successfully.')
      setShowOtpModal(false)
      setOtp('')
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Verification failed.')
    } finally { setOtpLoading(false) }
  }

  const handleResendOtp = async () => {
    setResending(true)
    try {
      const r = await settingsApi.changePassword(form)
      showToast('success', r.data.message || 'A new verification code has been sent.')
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to resend code.')
    } finally { setResending(false) }
  }

  const s = strength(form.new_password)

  return (
    <div className="settings-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ACCOUNT</div>
          <h1>Settings</h1>
          <p className="muted">Manage your account security and preferences.</p>
        </div>
      </div>

      <div className="settings-layout">
        <div className="panel settings-panel">
          <div className="panel-head">
            <div>
              <span className="muted">Security</span>
              <h3>Change Password</h3>
            </div>
            <Lock size={18} className="muted"/>
          </div>

          <form onSubmit={handleRequestOtp} className="settings-form">
            <PwdField label="Current Password" name="current_password" value={form.current_password} onChange={set} show={show.current} onToggle={() => toggle('current')} required/>
            <div>
              <PwdField label="New Password" name="new_password" value={form.new_password} onChange={set} show={show.new} onToggle={() => toggle('new')} required/>
              {form.new_password && (
                <div className="pwd-strength">
                  <div className="strength-bar">
                    {[1,2,3,4].map(i => <span key={i} className={`bar-seg ${s >= i ? strengthClass(s) : ''}`}/>)}
                  </div>
                  <span className={`strength-label ${strengthClass(s)}`}>{strengthLabel(s)}</span>
                </div>
              )}
            </div>
            <PwdField label="Confirm New Password" name="confirm_password" value={form.confirm_password} onChange={set} show={show.confirm} onToggle={() => toggle('confirm')} required/>

            <button type="submit" className="button primary" disabled={loading}>
              <ShieldCheck size={15}/> {loading ? 'Sending code…' : 'Continue'}
            </button>
          </form>
        </div>
      </div>

      {showOtpModal && (
        <div className="modal-backdrop">
          <div className="modal-box bug-modal">
            <div className="modal-head">
              <div className="modal-title"><Key size={18}/> Verify OTP</div>
              <button className="icon-button" onClick={() => setShowOtpModal(false)}><X size={18}/></button>
            </div>

            <form onSubmit={handleVerifyOtp} className="modal-body">
              <p className="muted" style={{ fontSize: '13px', marginBottom: '15px' }}>
                We've sent a 6-digit verification code to your registered email address. Enter it below to authorize the password change.
              </p>

              <label className="field">
                <span>Verification Code</span>
                <input
                  name="otp"
                  maxLength={6}
                  placeholder="000000"
                  value={otp}
                  onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
                  style={{ textAlign: 'center', fontSize: '20px', letterSpacing: '8px', fontWeight: 'bold' }}
                  required
                  autoFocus
                />
              </label>

              <div className="screenshot-row" style={{ justifyContent: 'space-between', marginTop: '10px' }}>
                <button type="button" className="button secondary" onClick={handleResendOtp} disabled={resending}>
                  <RefreshCw size={14} className={resending ? 'spinner' : ''}/> {resending ? 'Resending…' : 'Resend Code'}
                </button>
              </div>

              <div className="modal-footer">
                <button type="button" className="button ghost" onClick={() => setShowOtpModal(false)} disabled={otpLoading}>
                  Cancel
                </button>
                <button type="submit" className="button primary" disabled={otpLoading}>
                  {otpLoading ? 'Verifying…' : 'Verify & Change'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function PwdField({ label, name, value, onChange, show, onToggle, required }) {
  return (
    <label className="field" style={{ position: 'relative', display: 'block' }}>
      <span>{label}</span>
      <div style={{ position: 'relative' }}>
        <input name={name} type={show ? 'text' : 'password'} value={value} onChange={onChange} required={required} autoComplete="new-password" style={{ paddingRight: '40px' }}/>
        <button type="button" onClick={onToggle} className="eye-toggle" tabIndex={-1}>{show ? <EyeOff size={16}/> : <Eye size={16}/>}</button>
      </div>
    </label>
  )
}
