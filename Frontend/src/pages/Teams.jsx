import { useEffect, useMemo, useState } from 'react'
import { Network, Users } from 'lucide-react'
import { organizationApi } from '../services/api'
import Loading from '../components/Loading'

function flattenMembers(node) {
  return (node.children || []).flatMap(child => [child, ...flattenMembers(child)])
}

export default function Teams() {
  const [tree, setTree] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    organizationApi.tree()
      .then(response => setTree(Array.isArray(response.data) ? response.data : []))
      .catch(err => setError(err.response?.data?.detail || 'Unable to load teams.'))
  }, [])

  const teams = useMemo(() => (tree || []).map(lead => ({
    lead,
    members: flattenMembers(lead)
  })), [tree])

  if (!tree) return error ? <div className="empty-state"><h3>Unable to load teams</h3><p>{error}</p></div> : <Loading />

  return <div className="dashboard">
    <div className="page-heading"><div><div className="eyebrow">COMPANY STRUCTURE</div><h1>Teams</h1><p className="muted">View each team leader and the members assigned to their team.</p></div></div>
    {teams.length ? <div className="teams-grid">{teams.map(({ lead, members }) => <section className="panel team-card" key={lead.id}>
      <div className="team-card-head"><div className="company-dot"><Network size={18}/></div><div><h3>{lead.name}</h3><p>{lead.email}</p></div><span className="role-chip">{lead.role === 'manager' ? 'Team Leader' : 'Unassigned'}</span></div>
      <div className="team-members-head"><span><Users size={15}/> {members.length} {members.length === 1 ? 'member' : 'members'}</span></div>
      {members.length ? <div className="team-member-list">{members.map(member => <div className="team-member-row" key={member.id}><span className="avatar small">{member.name?.[0] || '?'}</span><span><b>{member.name || 'Unnamed member'}</b><small>{member.email}</small></span><span className="status-pill">{member.role === 'manager' ? 'Team Leader' : 'Member'}</span></div>)}</div> : <div className="empty-inline">No members assigned to this team.</div>}
    </section>)}</div> : <section className="panel empty-state"><div className="empty-icon"><Network size={22}/></div><h3>No teams yet</h3><p>Assign team leaders and members to see teams here.</p></section>}
  </div>
}
