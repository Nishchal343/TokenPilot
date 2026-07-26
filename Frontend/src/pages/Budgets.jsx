import { useEffect, useState } from 'react'
import { Check, IndianRupee, Eye, KeyRound, X, Activity, Clock3, ShieldCheck, Users } from 'lucide-react'
import { apiKeyRequestApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import StatusBadge from '../components/StatusBadge'

const statusLabels = { PENDING_COMPANY: 'Pending Approval', APPROVED: 'Approved', REJECTED: 'Rejected' }

export default function Budgets() {
  const { user } = useAuth()
  return user?.type === 'company' ? <CompanyApprovalCenter /> : <TeamLeaderRequests />
}

function TeamLeaderRequests() {
  const { showToast } = useToast()
  const [requests, setRequests] = useState(null)
  const [error, setError] = useState('')
  const [budgets, setBudgets] = useState({})
  const [details, setDetails] = useState(null)
  const [working, setWorking] = useState(null)

  const load = () => apiKeyRequestApi.teamLeader().then(response => setRequests(Array.isArray(response.data) ? response.data : [])).catch(err => setError(err.response?.data?.detail || 'Unable to load pending requests.'))
  useEffect(() => { load() }, [])

  const action = (request, type) => {
    const reason = type === 'reject' ? window.prompt('Rejection reason is required:') : undefined
    if (type === 'reject' && !reason?.trim()) return
    setWorking(request.id)
    apiKeyRequestApi.teamLeaderAction(request.id, { action: type, modified_budget: Number(budgets[request.id] || request.requested_budget), reason })
      .then(() => { showToast('success', type === 'approve' ? 'Request advanced to company approval.' : 'Request rejected.'); load() })
      .catch(err => showToast('error', err.response?.data?.detail || 'Unable to update request.'))
      .finally(() => setWorking(null))
  }

  if (!requests) return error ? <div className="empty-state">{error}</div> : <Loading />
  const pending = requests.length
  const totalBudget = requests.reduce((sum, request) => sum + Number(budgets[request.id] || request.requested_budget || 0), 0)
  return <div className="dashboard">
    <div className="page-heading page-heading-enhanced"><div><div className="eyebrow"><Activity size={13}/> TEAM GOVERNANCE</div><h1>Pending API Requests</h1><p className="muted">Review and budget AI access requests from your team.</p></div><span className="live-indicator"><i/> Live queue</span></div>
    <div className="approval-metrics approval-metrics-individual"><Metric icon={Clock3} label="Awaiting review" value={pending} tone="purple"/><Metric icon={IndianRupee} label="Requested allocation" value={`₹${totalBudget.toLocaleString('en-IN')}`} tone="blue"/></div>
    <section className="panel table-panel approval-panel">{requests.length ? <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Tier</th><th>Model</th><th>Requested Budget</th><th>Current Status</th><th>Actions</th></tr></thead><tbody>{requests.map(request => <tr key={request.id}><td><b>{request.employee_name || `Employee #${request.employee_id}`}</b></td><td>{request.requested_tier}</td><td>{request.requested_model}</td><td><input className="inline-input" type="number" min="1" value={budgets[request.id] ?? request.requested_budget} onChange={e => setBudgets({ ...budgets, [request.id]: e.target.value })}/></td><td><StatusBadge status={request.status}/></td><td><div className="approval-actions"><button className="icon-button" title="View Details" onClick={() => setDetails(details === request.id ? null : request.id)}><Eye size={15}/></button><button className="button primary compact-button" disabled={working === request.id} onClick={() => action(request, 'approve')}><Check size={14}/> Approve</button><button className="button secondary compact-button" disabled={working === request.id} onClick={() => action(request, 'reject')}><X size={14}/> Reject</button></div></td></tr>)}</tbody></table></div> : <div className="empty-state"><div className="empty-icon"><IndianRupee size={22}/></div><h3>No pending requests</h3><p>New team member API requests will appear here.</p></div>}{details && (() => { const request = requests.find(item => item.id === details); return request ? <div className="request-detail"><b>Reason</b><p>{request.reason}</p><span className="muted">Requested on {new Date(request.created_at).toLocaleString()}</span></div> : null })()}</section>
  </div>
}

function CompanyApprovalCenter() {
  const { showToast } = useToast()
  const [requests, setRequests] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({ provider: 'OpenAI', api_key: '', final_budget: '' })
  const [working, setWorking] = useState(null)

  const load = () => apiKeyRequestApi.companyRequests().then(response => setRequests(Array.isArray(response.data) ? response.data : [])).catch(err => setError(err.response?.data?.detail || 'Unable to load API key requests.'))
  useEffect(() => { load() }, [])

  const approve = request => {
    setWorking(request.id)
    apiKeyRequestApi.companyAction(request.id, { action: 'approve', provider: form.provider, api_key: form.api_key, final_budget: Number(form.final_budget || request.leader_modified_budget || request.requested_budget) })
      .then(() => { showToast('success', 'API key activated and access granted.'); setSelected(null); setForm({ provider: 'OpenAI', api_key: '', final_budget: '' }); load() })
      .catch(err => showToast('error', err.response?.data?.detail || 'Unable to approve request.'))
      .finally(() => setWorking(null))
  }
  const reject = request => { const reason = window.prompt('Rejection reason is required:'); if (!reason?.trim()) return; setWorking(request.id); apiKeyRequestApi.companyAction(request.id, { action: 'reject', reason }).then(() => { showToast('success', 'Request rejected.'); load() }).catch(err => showToast('error', err.response?.data?.detail || 'Unable to reject request.')).finally(() => setWorking(null)) }

  if (!requests) return error ? <div className="empty-state">{error}</div> : <Loading />
  const pending = requests.filter(request => request.status === 'PENDING_COMPANY').length
  const active = requests.filter(request => request.status === 'APPROVED').length
  const allocated = requests.reduce((sum, request) => sum + Number(request.company_final_budget || request.leader_modified_budget || request.requested_budget || 0), 0)
  return <div className="dashboard">
    <div className="page-heading page-heading-enhanced"><div><div className="eyebrow"><ShieldCheck size={13}/> COMPANY GOVERNANCE</div><h1>API Key Approval Center</h1><p className="muted">Activate governed AI access after team leader review.</p></div><span className="live-indicator"><i/> Approval center</span></div>
    <div className="approval-metrics"><Metric icon={Clock3} label="Awaiting approval" value={pending} tone="purple"/><Metric icon={IndianRupee} label="Budget in Review" value={`₹${allocated.toLocaleString('en-IN')}`} tone="blue"/><Metric icon={ShieldCheck} label="Approved Budgets" value={active} tone="green"/><Metric icon={Activity} label="Approval Workflow" value="2-Step Approval" tone="orange"/></div>
    <section className="panel table-panel approval-panel">{requests.length ? <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Team Leader</th><th>Tier</th><th>Model</th><th>Leader Budget</th><th>Status</th><th>Actions</th></tr></thead><tbody>{requests.map(request => <tr key={request.id}><td>{request.employee_name || `Employee #${request.employee_id}`}</td><td>{request.team_leader_name || `Leader #${request.team_leader_id}`}</td><td>{request.requested_tier}</td><td>{request.requested_model}</td><td>₹{Number(request.leader_modified_budget || request.requested_budget || 0).toLocaleString('en-IN')}</td><td><StatusBadge status={request.status}/></td><td>{request.status === 'PENDING_COMPANY' ? <button className="button primary compact-button" onClick={() => { setSelected(request.id); setForm({ provider: 'OpenAI', api_key: '', final_budget: String(request.leader_modified_budget || request.requested_budget) }) }}><KeyRound size={14}/> Review</button> : <span className="muted">Complete</span>}</td></tr>)}</tbody></table></div> : <div className="empty-state"><div className="empty-icon"><KeyRound size={22}/></div><h3>No requests awaiting approval</h3><p>Team leader-approved requests will appear here.</p></div>}{selected && (() => { const request = requests.find(item => item.id === selected); return request ? <div className="approval-editor"><div className="panel-head"><h3>Activate {request.requested_model} access</h3><button className="icon-button" onClick={() => setSelected(null)}><X size={16}/></button></div><div className="form-grid"><label className="field"><span>Provider</span><select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })}>{['OpenAI', 'Gemini', 'Claude', 'Groq', 'Azure OpenAI', 'OpenRouter', 'Other'].map(provider => <option key={provider}>{provider}</option>)}</select></label><label className="field"><span>API Key</span><input required type="password" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} placeholder="Stored encrypted" /></label><label className="field"><span>Final Budget</span><input required min="1" type="number" value={form.final_budget} onChange={e => setForm({ ...form, final_budget: e.target.value })}/></label></div><div className="form-actions"><button className="button secondary" onClick={() => reject(request)} disabled={working === request.id}>Reject</button><button className="button primary" onClick={() => approve(request)} disabled={working === request.id}><Check size={15}/> Approve & Activate</button></div></div> : null })()}</section>
  </div>
}

function Metric({ icon: Icon, label, value, tone }) {
  return <div className="approval-metric"><span className={`metric-icon ${tone}`}><Icon size={17}/></span><span><small>{label}</small><strong>{value}</strong></span></div>
}
