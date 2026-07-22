import { ArrowLeft, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { roleHome, useAuth } from '../contexts/AuthContext'

export default function ComingSoon({ title }) {
  const navigate = useNavigate()
  const { user } = useAuth()

  return (
    <div className="page-empty coming-soon">
      <div className="empty-icon"><Sparkles size={22}/></div>
      <div className="eyebrow">TOKENPILOT WORKSPACE</div>
      <h1>{title}</h1>
      <h2>Coming Soon</h2>
      <p>This feature is currently under development and will be available in a future update.</p>
      <button className="button primary" onClick={() => navigate(roleHome(user))}>
        <ArrowLeft size={16}/> Back to Dashboard
      </button>
    </div>
  )
}
