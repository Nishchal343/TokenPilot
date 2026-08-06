import { Bot, Code2, KeyRound, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function AIWorkspace() {
  const { user } = useAuth()
  const root = user?.type === 'company' ? '/dashboard/company' : user?.role === 'manager' ? '/dashboard/team-leader' : '/dashboard/member'
  return <div className="dashboard workspace-home"><div className="page-heading page-heading-enhanced"><div><span className="eyebrow">TOKENPILOT WORKSPACE</span><h1>Build with your approved AI.</h1><p className="muted">A secure place for conversations and code, powered by your organization’s provider or your own private key.</p></div><span className="live-indicator"><i/> Secure by design</span></div><div className="workspace-choice-grid"><section className="workspace-choice"><div className="workspace-choice-icon"><Bot size={25}/></div><span className="eyebrow">AI CHAT</span><h2>Think in conversation.</h2><p>Chat with AI using your organization’s approved provider or a personal API key when no company provider is available.</p><Link className="button primary" to={`${root}/ai-workspace/chat`}>Open Chat <Sparkles size={16}/></Link></section><section className="workspace-choice"><div className="workspace-choice-icon blue"><Code2 size={25}/></div><span className="eyebrow">AI IDE</span><h2>Turn ideas into code.</h2><p>A focused coding workspace with Monaco Editor, a file explorer, and an AI assistant beside your work.</p><Link className="button primary" to={`${root}/ai-workspace/ide`}>Open IDE <Code2 size={16}/></Link></section></div><div className="workspace-security-note"><KeyRound size={18}/><span>Your API secrets are encrypted and are never returned to the browser.</span></div></div>
}
