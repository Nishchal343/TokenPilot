import { useEffect, useState } from 'react'
import { CircleDollarSign, RotateCcw, Save } from 'lucide-react'
import { budgetApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import { formatCurrency } from '../utils/formatters'
import PreOrganizationOnboarding from '../components/PreOrganizationOnboarding'

export default function Budgets() {
  const { user } = useAuth(); const company = user?.type === 'company'; const manager = user?.role === 'manager'; const [items, setItems] = useState(null); const [error, setError] = useState('')
  const preOrganization = user?.type === 'employee' && !user?.company_id
  const { showToast } = useToast()
  const load = () => { const fn = company ? budgetApi.company : manager ? budgetApi.team : budgetApi.me; fn().then(r => setItems(Array.isArray(r.data) ? r.data : [r.data])).catch(e => setError(e.response?.data?.detail || 'Unable to load budgets.')) }
  useEffect(() => { if (!preOrganization) load() }, [preOrganization])
  const update = (id, monthly_limit) => (manager ? budgetApi.teamUpdate(id, { monthly_limit: Number(monthly_limit) }) : budgetApi.update(id, { monthly_limit: Number(monthly_limit) })).then(() => { showToast('success', 'Budget limit updated successfully.'); load() }).catch(e => showToast('error', e.response?.data?.detail || 'Unable to update budget.'))
  if (preOrganization) return <PreOrganizationOnboarding variant="budget" />
  if (!items) return error ? <div className="empty-state">{error}</div> : <Loading/>
  const total = sum(items, 'monthly_limit')
  const managerBudget = manager ? items.find(item => item.employee_id === user.id) : null
  const teamMembers = manager ? items.filter(item => item.employee_id !== user.id) : []
  return <div className="dashboard"><div className="page-heading"><div><div className="eyebrow">TOKEN GOVERNANCE</div><h1>{manager ? 'Team budgets.' : 'Budget control.'}</h1><p className="muted">{manager ? 'Allocate budgets only within your assigned team.' : 'Keep AI usage intentional, visible, and ready to scale.'}</p></div>{company && <button className="button secondary" onClick={() => budgetApi.reset().then(() => { showToast('success', 'Monthly token usage has been reset.'); load() }).catch(e => showToast('error', e.response?.data?.detail || 'Unable to reset token usage.'))}><RotateCcw size={16}/> Reset monthly usage</button>}</div>{manager && <div className="stats-grid"><Stat label="Allocated Team Budget" value={managerBudget ? compact(managerBudget.monthly_limit) : '—'} /><Stat label="Budget Used" value={managerBudget ? compact(managerBudget.used_tokens) : '—'} /><Stat label="Remaining Budget" value={managerBudget ? compact(managerBudget.remaining_tokens) : '—'} /><Stat label="Total Employees" value={teamMembers.length} /></div>}<div className="budget-hero"><div><span className="muted">{company ? 'Organization allocation' : manager ? 'Team allocation' : 'Your allocation'}</span><strong>{total == null ? 'No data available yet' : compact(total)} <small>tokens / month</small></strong></div><CircleDollarSign size={34}/></div><section className="panel table-panel"><div className="panel-head"><h3>{company ? 'All organization budgets' : manager ? 'Assigned team budgets' : 'My budget'}</h3><span className="muted">{items.length || 'No'} {items.length === 1 ? 'member' : 'members'}</span></div>{items.length ? <div className="table-wrap"><table><thead><tr><th>Member</th><th>Monthly limit</th><th>Used</th><th>Remaining</th><th>Requests</th><th>Cost</th>{(company || manager) && <th/>}</tr></thead><tbody>{items.map(x => <tr key={x.id}><td><span className="table-person"><span className="avatar small">{String(x.employee_id).slice(-1)}</span><b>Employee #{x.employee_id}{manager && x.employee_id === user.id ? ' (You)' : ''}</b></span></td><td>{(company || (manager && x.employee_id !== user.id)) ? <input className="inline-input" type="number" defaultValue={x.monthly_limit ?? ''} placeholder="Not set" onBlur={e => e.target.value && update(x.employee_id, e.target.value)}/> : display(x.monthly_limit, compact)}</td><td>{display(x.used_tokens, compact)}</td><td><span className="positive">{display(x.remaining_tokens, compact)}</span></td><td>{display(x.total_requests)}</td><td>{display(x.estimated_cost, formatCurrency)}</td>{(company || manager) && <td><Save size={15} className="muted"/></td>}</tr>)}</tbody></table></div> : <div className="empty-state"><h3>No budgets available yet</h3><p>Assign a budget to see token usage and cost data here.</p></div>}</section></div>
}
function Stat({ label, value }) { return <div className="stat-card"><div><span className="muted">{label}</span><strong>{value}</strong></div></div> }
const display = (value, formatter = value => value) => value == null ? '—' : formatter(value)
const sum = (items, field) => items.some(item => typeof item?.[field] === 'number') ? items.reduce((total, item) => total + (typeof item?.[field] === 'number' ? item[field] : 0), 0) : null
const compact = n => Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(n))
