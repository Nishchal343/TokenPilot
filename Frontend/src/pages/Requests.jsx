import { useEffect, useState } from 'react'
import { ClipboardList, Send } from 'lucide-react'
import { apiKeyRequestApi } from '../services/api'
import StatusBadge from '../components/StatusBadge'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'

const initialForm = { requested_tier: 'MEDIUM', requested_model: '', requested_budget: '', reason: '' }
const statusLabels = {
  PENDING_TEAM_LEADER: 'Pending Approval',
  PENDING_COMPANY: 'Pending Approval',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  REJECTED_BY_TEAM_LEADER: 'Rejected'
}

export default function Requests() {
  const { showToast } = useToast()
  const [form, setForm] = useState(initialForm)
  const [requests, setRequests] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = () => apiKeyRequestApi.mine().then(response => setRequests(Array.isArray(response.data) ? response.data : [])).catch(err => setError(err.response?.data?.detail || 'Unable to load requests.'))
  useEffect(() => { load() }, [])

  const submit = event => {
    event.preventDefault()
    setSubmitting(true)
    apiKeyRequestApi.create({ ...form, requested_budget: Number(form.requested_budget) })
      .then(() => { showToast('success', 'AI API key request submitted.'); setForm(initialForm); load() })
      .catch(err => showToast('error', err.response?.data?.detail || 'Unable to submit request.'))
      .finally(() => setSubmitting(false))
  }

  if (!requests) return error ? <div className="empty-state">{error}</div> : <Loading />

  return <div className="dashboard">
    <div className="page-heading"><div><div className="eyebrow">AI ACCESS CONTROL</div><h1>Request AI API Key</h1><p className="muted">Request governed access to an AI provider for your work.</p></div></div>
    <section className="panel request-form-panel">
      <form onSubmit={submit}>
        <div className="form-grid">
          <label className="field"><span>AI Tier</span><select value={form.requested_tier} onChange={e => setForm({ ...form, requested_tier: e.target.value })}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option></select></label>
          <label className="field"><span>Model Name</span><input required value={form.requested_model} onChange={e => setForm({ ...form, requested_model: e.target.value })} placeholder="GPT-5, Gemini 2.5 Pro, Claude Opus" /></label>
          <label className="field"><span>Requested Budget</span><input required min="1" type="number" value={form.requested_budget} onChange={e => setForm({ ...form, requested_budget: e.target.value })} placeholder="Estimated monthly usage" /><small className="muted">Estimated monthly token usage</small></label>
          <label className="field full-width"><span>Reason</span><textarea required rows="4" value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} placeholder="Tell your team why this access is needed." /></label>
        </div>
        <div className="form-actions"><button className="button primary" disabled={submitting}>{submitting ? 'Submitting...' : <><Send size={16}/> Submit Request</>}</button></div>
      </form>
    </section>
    <section className="panel table-panel request-history"><div className="panel-head"><h3><ClipboardList size={17}/> Submitted Requests</h3></div>{requests.length ? <div className="table-wrap"><table><thead><tr><th>Status</th><th>Requested Model</th><th>Budget</th><th>Current Stage</th><th>Submission Date</th></tr></thead><tbody>{requests.map(request => <tr key={request.id}><td><StatusBadge status={request.status}/></td><td>{request.requested_model}</td><td>{request.company_final_budget || request.leader_modified_budget || request.requested_budget}</td><td>{request.status === 'APPROVED' ? 'Access active' : request.status.includes('REJECTED') ? request.rejection_reason : statusLabels[request.status]}</td><td>{new Date(request.created_at).toLocaleDateString()}</td></tr>)}</tbody></table></div> : <div className="empty-state"><div className="empty-icon"><ClipboardList size={22}/></div><h3>No requests yet</h3><p>Your submitted requests will appear here.</p></div>}</section>
  </div>
}
