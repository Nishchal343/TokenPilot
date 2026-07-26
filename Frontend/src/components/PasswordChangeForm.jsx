import { useState } from 'react'
import { Eye, EyeOff, Key, Lock, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { settingsApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'

export default function PasswordChangeForm({ showHeader = true }) {
  const { showToast } = useToast()
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [otp, setOtp] = useState('')
  const [show, setShow] = useState({ current: false, new: false, confirm: false })
  const [loading, setLoading] = useState(false)
  const [otpLoading, setOtpLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [otpOpen, setOtpOpen] = useState(false)

  const update = e => setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  const toggle = key => setShow(prev => ({ ...prev, [key]: !prev[key] }))

  const requestOtp = async e => {
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
      const response = await settingsApi.changePassword(form)
      setOtpOpen(true)
      showToast('success', response.data?.message || 'Verification code sent to your email.')
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Unable to request a password change. Check the current password and email service.')
    } finally {
      setLoading(false)
    }
  }

  const verifyOtp = async e => {
    e.preventDefault()
    if (!/^\d{6}$/.test(otp)) {
      showToast('error', 'Please enter a valid 6-digit verification code.')
      return
    }
    setOtpLoading(true)
    try {
      const response = await settingsApi.changePasswordVerify({ otp, new_password: form.new_password, confirm_password: form.confirm_password })
      showToast('success', response.data?.message || 'Password updated successfully.')
      setOtpOpen(false)
      setOtp('')
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Invalid or expired verification code.')
    } finally {
      setOtpLoading(false)
    }
  }

  const resend = async () => {
    setResending(true)
    try {
      const response = await settingsApi.changePassword(form)
      showToast('success', response.data?.message || 'A new verification code has been sent.')
    } catch (error) {
      showToast('error', error.response?.data?.detail || 'Unable to resend verification code.')
    } finally {
      setResending(false)
    }
  }

  return <>
    <div className="panel settings-panel">
      {showHeader && <div className="panel-head">
        <div><span className="muted">Password security</span><h3>Change Password</h3></div>
        <Lock size={18} className="muted" />
      </div>}
      <form onSubmit={requestOtp} className="settings-form">
        <PasswordField label="Current Password" name="current_password" value={form.current_password} onChange={update} show={show.current} onToggle={() => toggle('current')} />
        <PasswordField label="New Password" name="new_password" value={form.new_password} onChange={update} show={show.new} onToggle={() => toggle('new')} />
        <PasswordField label="Confirm New Password" name="confirm_password" value={form.confirm_password} onChange={update} show={show.confirm} onToggle={() => toggle('confirm')} />
        <button type="submit" className="button primary" disabled={loading}><ShieldCheck size={15} /> {loading ? 'Sending code…' : 'Continue'}</button>
      </form>
    </div>

    {otpOpen && <div className="modal-backdrop">
      <div className="modal-box bug-modal">
        <div className="modal-head"><div className="modal-title"><Key size={18} /> Verify OTP</div><button className="icon-button" onClick={() => setOtpOpen(false)}><X size={18} /></button></div>
        <form onSubmit={verifyOtp} className="modal-body">
          <p className="muted" style={{ fontSize: '13px', marginBottom: '15px' }}>Enter the 6-digit code sent to your registered email to authorize this password change.</p>
          <label className="field"><span>Verification Code</span><input value={otp} maxLength={6} placeholder="000000" onChange={e => setOtp(e.target.value.replace(/\D/g, ''))} style={{ textAlign: 'center', fontSize: '20px', letterSpacing: '8px', fontWeight: 'bold' }} autoFocus required /></label>
          <button type="button" className="button secondary" onClick={resend} disabled={resending}><RefreshCw size={14} /> {resending ? 'Resending…' : 'Resend Code'}</button>
          <div className="modal-footer"><button type="button" className="button ghost" onClick={() => setOtpOpen(false)} disabled={otpLoading}>Cancel</button><button type="submit" className="button primary" disabled={otpLoading}>{otpLoading ? 'Verifying…' : 'Verify & Change'}</button></div>
        </form>
      </div>
    </div>}
  </>
}

function PasswordField({ label, name, value, onChange, show, onToggle }) {
  return <label className="field"><span>{label}</span><div style={{ position: 'relative' }}><input name={name} type={show ? 'text' : 'password'} value={value} onChange={onChange} required autoComplete="new-password" style={{ paddingRight: '40px' }} /><button type="button" onClick={onToggle} className="eye-toggle" tabIndex={-1}>{show ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>
}
