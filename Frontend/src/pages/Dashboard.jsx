import { useEffect, useState } from 'react'
import { ArrowUpRight, CircleDollarSign, Cpu, Database, Gauge, GitBranch, Globe2, LockKeyhole } from 'lucide-react'
import { dashboardApi } from '../services/api'
import Loading from '../components/Loading'
import ErrorState from '../components/ErrorState'
import StatCard from '../components/StatCard'
import { formatCurrency } from '../utils/formatters'
import { useAuth } from '../contexts/AuthContext'
import PreOrganizationOnboarding from '../components/PreOrganizationOnboarding'

const number = value => Number(value || 0).toLocaleString()

function CacheMetricCard({ title, icon: Icon, data, global }) {
  const values = data || {}
  return <section className="cache-metric-card">
    <header><span className={global ? 'global-cache-icon' : 'private-cache-icon'}><Icon size={17}/></span><div><span className="muted">{global ? 'SHARED TENANT CACHE' : 'CONTEXT-SPECIFIC CACHE'}</span><h3>{title}</h3></div></header>
    <div className="cache-metric-grid">
      <span>Hits <b>{number(values.hits)}</b></span><span>Misses <b>{number(values.misses)}</b></span>
      <span>Hit rate <b>{values.hit_rate || 0}%</b></span><span>Exact hits <b>{number(values.exact_hits)}</b></span>
      <span>Semantic hits <b>{number(values.semantic_hits)}</b></span><span>Tokens saved <b>{number(values.tokens_saved)}</b></span>
      <span>API calls avoided <b>{number(values.api_calls_avoided)}</b></span><span>Cached entries <b>{number(values.entries)}</b></span>
      {global && <><span>Current size <b>{number(values.size)}</b></span><span>TTL <b>{number(Math.round(Number(values.ttl_seconds || 0) / 3600))}h</b></span></>}
    </div>
  </section>
}

export default function Dashboard({ type }) {
  const { user } = useAuth(); const [data, setData] = useState(); const [optimization, setOptimization] = useState(); const [error, setError] = useState()
  const load = () => { setError(null); const fn = type === 'company' ? dashboardApi.company : type === 'manager' ? dashboardApi.manager : dashboardApi.employee; fn().then(response => setData(response.data)).catch(setError); dashboardApi.optimization().then(response => setOptimization(response.data)).catch(() => {}) }
  useEffect(() => { if (type !== 'employee' || user?.company_id) load() }, [type, user?.company_id])
  if (type === 'employee' && !user?.company_id) return <PreOrganizationOnboarding />
  if (error) return <ErrorState error={error} onRetry={load}/>
  if (!data) return <Loading/>
  const company = type === 'company'; const manager = type === 'manager'; const used = company ? data.total_tokens_used : manager ? data.team_tokens_used : data.used_tokens; const requests = company ? data.total_ai_requests : manager ? data.total_team_requests : data.total_requests; const cost = company ? data.estimated_ai_cost : manager ? data.estimated_team_cost : data.estimated_cost
  const cache = optimization?.cache_dashboard || {}; const totalCache = cache.total_optimization || {}
  return <div className="dashboard dashboard-refined"><div className="page-heading"><div><div className="eyebrow">{company ? 'COMPANY OVERVIEW' : manager ? 'TEAM LEAD OVERVIEW' : 'PERSONAL OVERVIEW'}</div><h1>{company ? `Hello, ${data.company_name}.` : `Hello, ${data.manager_name || data.employee_name}.`}</h1><p className="muted">AI usage and optimization performance in one place.</p></div></div><div className="stats-grid dashboard-overview-stats"><StatCard label="Requests" value={number(requests)} icon={GitBranch} tone="purple"/><StatCard label="Tokens used" value={number(used)} icon={Cpu} tone="blue"/><StatCard label="Estimated cost" value={formatCurrency(cost)} icon={CircleDollarSign} tone="orange"/><StatCard label="Tokens saved" value={number(optimization?.total_tokens_saved)} icon={Gauge} tone="green"/></div><section className="panel optimization-dashboard-panel"><div className="panel-head"><div><span className="muted">OPTIMIZATION ENGINE</span><h3>Measured savings</h3></div><ArrowUpRight className="positive" size={18}/></div><div className="stats-grid optimization-stats"><StatCard label="Average reduction" value={`${optimization?.average_token_reduction || 0}%`} icon={Gauge} tone="purple"/><StatCard label="Cost saved" value={formatCurrency(optimization?.estimated_cost_saved)} icon={CircleDollarSign} tone="green"/><StatCard label="Cache hits" value={number(optimization?.cache_hits)} icon={GitBranch} tone="blue"/><StatCard label="API calls avoided" value={number(optimization?.api_calls_avoided)} icon={Cpu} tone="orange"/></div><div className="optimization-breakdown">{Object.entries(optimization?.breakdown || {}).filter(([stage]) => stage.toLowerCase() !== 'code').map(([stage, saved]) => <div key={stage}><span>{stage}</span><b>{number(saved)} tokens</b><i><em style={{ width:`${Math.min(100, Number(saved || 0) / Math.max(1, Number(optimization?.total_tokens_saved || 1)) * 100)}%` }}/></i></div>)}</div></section><section className="panel cache-dashboard-panel"><div className="panel-head"><div><span className="muted">CACHE ANALYTICS</span><h3>Global and private cache</h3></div></div><div className="cache-metric-layout"><CacheMetricCard title="Global Cache" icon={Globe2} data={cache.global_cache} global/><CacheMetricCard title="Private Cache" icon={LockKeyhole} data={cache.private_cache}/></div><div className="total-cache-summary"><Database size={18}/><span><small>TOTAL OPTIMIZATION</small><b>{number(totalCache.cache_hits)} combined hits</b></span><span>Tokens saved <b>{number(totalCache.tokens_saved)}</b></span><span>Provider calls avoided <b>{number(totalCache.api_calls_avoided)}</b></span><span>Overall hit rate <b>{totalCache.cache_hit_rate || 0}%</b></span></div></section><section className="panel recent-optimization-panel"><div className="panel-head"><div><span className="muted">RECENT OPTIMIZATION ACTIVITY</span><h3>Latest requests</h3></div></div>{(optimization?.recent || []).length ? optimization.recent.slice().reverse().map(item => <div className="list-row" key={item.id}><span className="status-pill">{item.module}</span><span><b>{number(item.report?.saved_tokens)} tokens saved</b><small>{item.report?.reduction_percent || 0}% reduction</small></span><strong>{formatCurrency(item.report?.cost_saved)}</strong></div>) : <div className="empty-inline">Optimization analytics will appear after your first AI request.</div>}</section></div>
}
