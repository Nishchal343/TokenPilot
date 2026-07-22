import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Zap, Eye, EyeOff } from 'lucide-react'
import Logo from '../components/Logo'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const messages = { 
  login: ['Welcome back', 'Sign in to your workspace.'], 
  register: ['Create your workspace', 'Start making every token work harder.'], 
  verify: ['Verify your email', 'We’ve sent a 6-digit verification code to your email address.'], 
  forgot: ['Reset your password', 'We’ll send a verification code to your email.'], 
  reset: ['Choose a new password', 'Secure your workspace with a new password.'] 
}

export default function Auth({ mode = 'login' }) {
  const { authApi, login } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const { showToast } = useToast()
  
  const [kind, setKind] = useState(() => {
    const params = new URLSearchParams(loc.search)
    return params.get('kind') || 'company'
  })

  const [form, setForm] = useState(() => ({
    email: new URLSearchParams(loc.search).get('email') || '',
    otp: '',
    password: '',
    confirm_password: '',
    new_password: '',
    name: ''
  }))

  const [loading, setLoading] = useState(false)

  const set = e => setForm({ ...form, [e.target.name]: e.target.value })

  useEffect(() => {
    if (mode === 'verify') {
      showToast('success', 'Verification code sent successfully. Enter the OTP below to activate your TokenPilot account.')
    } else if (mode === 'reset' && loc.state?.successMessage) {
      showToast('success', loc.state.successMessage)
    }
  }, [mode, loc.state])

  const resendOtp = async () => {
    setLoading(true)
    try {
      const response = await authApi.forgot(kind, { email: form.email })
      showToast('success', response.data?.message || 'A new verification code has been sent to your email.')
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Could not resend code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const submit = async e => {
    e.preventDefault()
    setLoading(true)

    if (mode === 'reset') {
      if (!form.otp || form.otp.length !== 6) {
        showToast('error', 'OTP must be exactly 6 digits.')
        setLoading(false)
        return
      }
      if (form.new_password !== form.confirm_password) {
        showToast('error', 'Passwords do not match.')
        setForm(prev => ({ ...prev, new_password: '', confirm_password: '' }))
        setLoading(false)
        return
      }
      if (form.new_password.length < 8) {
        showToast('error', 'Password must be at least 8 characters long.')
        setLoading(false)
        return
      }
    }

    try {
      let response
      if (mode === 'login') {
        response = kind === 'company' ? await authApi.companyLogin(form) : await authApi.employeeLogin(form)
      } else if (mode === 'register') {
        response = kind === 'company' ? await authApi.companyRegister(form) : await authApi.employeeRegister(form)
      } else if (mode === 'verify') {
        response = kind === 'company' ? await authApi.companyVerify(form) : await authApi.employeeVerify(form)
      } else if (mode === 'forgot') {
        response = await authApi.forgot(kind, { email: form.email })
      } else {
        response = await authApi.reset(kind, {
          email: form.email,
          otp: form.otp,
          new_password: form.new_password,
          confirm_password: form.confirm_password
        })
      }

      if (response.data?.access_token) {
        if (mode === 'verify') {
          showToast('success', '✓ Email verified successfully. Welcome to TokenPilot!')
          setTimeout(() => { 
            login(response, form.email)
            nav(kind === 'company' ? '/dashboard/company' : '/dashboard/member', { replace: true })
          }, 900)
        } else {
          login(response, form.email)
          nav(kind === 'company' ? '/dashboard/company' : '/dashboard/member', { replace: true })
        }
      } else {
        if (mode === 'forgot') {
          const successMsg = response.data?.message || 'Verification OTP sent. Check your email for the code.'
          showToast('success', successMsg)
          setTimeout(() => {
            nav(`/reset?kind=${kind}&email=${form.email}`, { state: { successMessage: successMsg } })
          }, 1500)
        } else if (mode === 'reset') {
          showToast('success', response.data?.message || 'Password reset successfully.')
          setTimeout(() => {
            nav(`/login?kind=${kind}`)
          }, 1500)
        } else {
          showToast('success', response.data?.message || 'Verification is pending. Check your email for the code.')
          if (mode === 'register') {
            nav(`/verify?kind=${kind}&email=${form.email}`)
          }
        }
      }
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Something went wrong. Please try again.')
      setForm(prev => ({
        ...prev,
        password: '',
        confirm_password: '',
        new_password: ''
      }))
    } finally {
      setLoading(false)
    }
  }

  const title = mode === 'register' && kind === 'employee'
    ? ['Create your account', 'Verify your email to start using TokenPilot.']
    : messages[mode]
  
  return (
    <div className="auth-page">
      <div className="auth-visual">
        <Logo/>
        <div>
          <div className="eyebrow"><Zap size={14}/> Intelligence for intentional teams</div>
          <h1>Clarity is a<br/><span className="gradient-text">competitive edge.</span></h1>
          <p>Know what your AI costs. Give your people room to build.</p>
        </div>
        <small>© 2026 TokenPilot</small>
      </div>
      
      <div className="auth-panel">
        <div className="auth-form">
          <Logo/>
          <div className="auth-heading">
            <h2>{title[0]}</h2>
            <p>{title[1]}</p>
          </div>

          {['login', 'register'].includes(mode) && (
            <div className="segmented">
              <button type="button" className={kind === 'company' ? 'selected' : ''} onClick={() => setKind('company')}>Company</button>
              <button type="button" className={kind === 'employee' ? 'selected' : ''} onClick={() => setKind('employee')}>Employee</button>
            </div>
          )}

          <form onSubmit={submit}>
            {mode === 'register' && (
              <Field 
                name="name" 
                label="Full Name" 
                value={form.name} 
                onChange={set} 
                required
              />
            )}
            
            <Field 
              name="email" 
              label="Work email" 
              type="email" 
              value={form.email} 
              onChange={set} 
              required 
              readOnly={mode === 'reset'}
            />

            {['login', 'register'].includes(mode) && (
              <Field 
                name="password" 
                label="Password" 
                type="password" 
                value={form.password} 
                onChange={set} 
                required
              />
            )}

            {mode === 'register' && (
              <Field 
                name="confirm_password" 
                label="Confirm password" 
                type="password" 
                value={form.confirm_password} 
                onChange={set} 
                required
              />
            )}

            {mode === 'verify' && (
              <Field 
                name="otp" 
                label="Verification code" 
                value={form.otp} 
                onChange={set} 
                required
              />
            )}

            {mode === 'reset' && (
              <>
                <Field name="otp" label="Verification code" value={form.otp} onChange={set} required maxLength={6} pattern="[0-9]{6}"/>
                <Field name="new_password" label="New password" type="password" value={form.new_password} onChange={set} required/>
                <Field name="confirm_password" label="Confirm password" type="password" value={form.confirm_password} onChange={set} required/>
              </>
            )}

            {mode === 'reset' ? (
              <>
                <button className="button primary full" disabled={loading}>{loading ? 'Working…' : 'Reset password'}</button>
                <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                  <button type="button" className="button secondary full" onClick={resendOtp} disabled={loading}>Resend OTP</button>
                  <button type="button" className="button ghost full" onClick={() => nav(`/forgot?kind=${kind}&email=${form.email}`)} disabled={loading}>Back</button>
                </div>
              </>
            ) : (
              <button className="button primary full" disabled={loading}>
                {loading ? 'Working…' : mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : mode === 'forgot' ? 'Send code' : mode === 'verify' ? 'Verify email' : 'Reset password'}
              </button>
            )}
          </form>

          {mode === 'login' && (
            <div className="auth-links">
              <Link to={`/forgot?kind=${kind}`}>Forgot password?</Link>
              <span>New here? <Link to={`/register?kind=${kind}`}>{kind === 'employee' ? 'Create account' : 'Create workspace'}</Link></span>
            </div>
          )}
          
          {mode === 'register' && (
            <p className="auth-bottom">Already have an account? <Link to={`/login?kind=${kind}`}>Sign in</Link></p>
          )}

          {mode === 'forgot' && (
            <p className="auth-bottom"><Link to={`/login?kind=${kind}`}>Back to sign in</Link></p>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ name, label, type = 'text', value, onChange, required, readOnly, ...rest }) {
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword ? (show ? 'text' : 'password') : type

  return (
    <label className="field" style={{ position: 'relative', display: 'block' }}>
      <span>{label}</span>
      <div style={{ position: 'relative', width: '100%' }}>
        <input
          name={name}
          type={inputType}
          value={value}
          onChange={onChange}
          required={required}
          readOnly={readOnly}
          autoComplete={isPassword ? 'new-password' : 'off'}
          style={{ 
            paddingRight: isPassword ? '40px' : '12px',
            opacity: readOnly ? 0.65 : 1,
            cursor: readOnly ? 'not-allowed' : 'text'
          }}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow(!show)}
            style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 0,
              padding: 0,
              color: '#8b95aa',
              display: 'grid',
              placeItems: 'center',
              cursor: 'pointer'
            }}
          >
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        )}
      </div>
    </label>
  )
}
