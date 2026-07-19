import { useEffect, useState, useMemo } from 'react'
import { 
  ChevronLeft, 
  ChevronRight, 
  Search, 
  UserPlus, 
  User, 
  UserCheck, 
  Shield, 
  X, 
  Trash2, 
  Edit3, 
  Eye, 
  AlertCircle 
} from 'lucide-react'
import { organizationApi, invitationApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import PreOrganizationOnboarding from '../components/PreOrganizationOnboarding'

export default function Organization() {
  const { user } = useAuth()
  const { showToast } = useToast()
  
  const [members, setMembers] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Search, filter, sorting, pagination state
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [sortField, setSortField] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  // Modals state
  const [inviteModal, setInviteModal] = useState(false)
  const [detailModal, setDetailModal] = useState(null)
  const [editRoleModal, setEditRoleModal] = useState(null)
  const [removeConfirm, setRemoveConfirm] = useState(null)

  const isCompanyAdmin = user?.type === 'company'
  const isManager = user?.role === 'manager'
  const isPreOrganization = user?.type === 'employee' && !user?.company_id

  const loadMembers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await (isManager ? organizationApi.teamMembers() : organizationApi.members())
      setMembers(response.data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to load organization members.')
      showToast('error', 'Failed to load organization members.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!isPreOrganization) loadMembers()
  }, [isPreOrganization, isManager])

  // Filter, Sort, Paginate
  const processedMembers = useMemo(() => {
    if (!members) return []
    
    // 1. Search
    let result = members.filter(m => 
      m.name.toLowerCase().includes(query.toLowerCase()) || 
      m.email.toLowerCase().includes(query.toLowerCase()) ||
      (m.department && m.department.toLowerCase().includes(query.toLowerCase())) ||
      (m.designation && m.designation.toLowerCase().includes(query.toLowerCase()))
    )

    // 2. Filter by role
    if (roleFilter !== 'all') {
      result = result.filter(m => m.role === roleFilter)
    }

    // 3. Sort
    result.sort((a, b) => {
      let aVal = a[sortField] || ''
      let bVal = b[sortField] || ''
      if (sortField === 'name') {
        aVal = a.name.toLowerCase()
        bVal = b.name.toLowerCase()
      }
      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1
      return 0
    })

    return result
  }, [members, query, roleFilter, sortField, sortOrder])

  // Paginated chunk
  const paginatedMembers = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return processedMembers.slice(start, start + itemsPerPage)
  }, [processedMembers, currentPage])

  const totalPages = Math.ceil(processedMembers.length / itemsPerPage) || 1

  // Page index resets when query/filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [query, roleFilter])

  const handleRemove = async (memberId) => {
    try {
      await (isManager ? organizationApi.removeTeamMember(memberId) : organizationApi.removeMember(memberId))
      showToast('success', 'Member removed from organization successfully.')
      setRemoveConfirm(null)
      loadMembers()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to remove member.')
    }
  }

  const handleUpdateRole = async (memberId, newRole, managerId) => {
    try {
      await organizationApi.updateRole(memberId, { role: newRole, manager_id: managerId })
      showToast('success', 'Member role updated successfully.')
      setEditRoleModal(null)
      loadMembers()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to update member role.')
    }
  }

  if (isPreOrganization) return <PreOrganizationOnboarding variant="organization" />
  if (loading && !members) return <Loading />

  return (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <div className="eyebrow">{isManager ? 'TEAM MANAGEMENT' : 'ORGANIZATION'}</div>
          <h1>{isManager ? 'My Team' : 'Active Members'}</h1>
          <p className="muted">{isManager ? 'Manage your assigned employees, budgets, permissions and invitations.' : 'Manage access, roles, and reporting lines for active workspace members.'}</p>
        </div>
        {(isCompanyAdmin || isManager) && (
          <button className="button primary" onClick={() => setInviteModal(true)}>
            <UserPlus size={16}/> Invite Member
          </button>
        )}
      </div>

      {error ? (
        <div className="empty-state">
          <AlertCircle size={32} className="muted" style={{ color: '#ff5978' }}/>
          <h3>Error Loading Members</h3>
          <p>{error}</p>
          <button className="button secondary" onClick={loadMembers} style={{ marginTop: '12px' }}>
            Retry
          </button>
        </div>
      ) : (
        <>
          {/* Filters & Toolbar */}
          <div className="toolbar" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '20px' }}>
            <div className="search wide" style={{ flex: '1', minWidth: '260px' }}>
              <Search size={16}/>
              <input 
                placeholder="Search name, email, department or designation..." 
                value={query} 
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '10px' }}>
              <select 
                className="inline-input" 
                value={roleFilter} 
                onChange={e => setRoleFilter(e.target.value)}
                style={{ width: '150px', background: '#141925', height: '40px', borderRadius: '10px', borderColor: '#252d3e', padding: '0 12px' }}
              >
                <option value="all">All Roles</option>
                <option value="manager">Managers</option>
                <option value="employee">Employees</option>
              </select>

              <select 
                className="inline-input" 
                value={`${sortField}-${sortOrder}`} 
                onChange={e => {
                  const [field, order] = e.target.value.split('-')
                  setSortField(field)
                  setSortOrder(order)
                }}
                style={{ width: '170px', background: '#141925', height: '40px', borderRadius: '10px', borderColor: '#252d3e', padding: '0 12px' }}
              >
                <option value="name-asc">Name (A-Z)</option>
                <option value="name-desc">Name (Z-A)</option>
                <option value="created_at-desc">Newest Joined</option>
                <option value="created_at-asc">Oldest Joined</option>
              </select>
            </div>
          </div>

          {/* Members Table */}
          <div className="panel table-panel">
            <div className="panel-head">
              <h3>{isManager ? 'Team Members' : 'Active Workspace Members'}</h3>
              <span className="muted">{processedMembers.length} {processedMembers.length === 1 ? 'member' : 'members'} found</span>
            </div>

            {loading ? (
              <div className="loading" style={{ minHeight: '200px' }}>
                <span className="spinner"></span> Loading workspace members...
              </div>
            ) : paginatedMembers.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon"><User size={20}/></div>
                <h3>No members found</h3>
                <p>No active workspace members match your search filters.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Member</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Joined Date</th>
                      <th>Last Login</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedMembers.map(m => {
                      const initial = (m.name || 'U')[0].toUpperCase()
                      return (
                        <tr key={m.id}>
                          <td>
                            <div className="table-person">
                              <span className={`avatar small ${m.role === 'manager' ? 'manager' : ''}`}>
                                {m.avatar_url ? (
                                  <img 
                                    src={`${import.meta.env.VITE_API_URL || ''}${m.avatar_url}`} 
                                    alt="avatar" 
                                    style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                                  />
                                ) : initial}
                              </span>
                              <div>
                                <b style={{ display: 'block', color: '#eef0f7' }}>{m.name}</b>
                                <small style={{ display: 'block', color: '#8b95aa', fontSize: '11px', marginTop: '2px' }}>{m.email}</small>
                              </div>
                            </div>
                          </td>
                          <td>
                            {m.role === 'manager' ? (
                              <span className="role-chip" style={{ color: '#c4b5fd', background: 'rgba(139, 92, 246, 0.12)', borderColor: 'rgba(139, 92, 246, 0.3)' }}>Manager</span>
                            ) : (
                              <span className="role-chip" style={{ color: '#a5afc2', background: 'rgba(41, 50, 71, 0.15)', borderColor: 'rgba(41, 50, 71, 0.4)' }}>Employee</span>
                            )}
                          </td>
                          <td>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#35d49a' }}>
                              <i className="dot green" style={{ margin: 0 }}/> Active
                            </span>
                          </td>
                          <td>
                            <small className="muted">
                              {m.created_at ? new Date(m.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'}
                            </small>
                          </td>
                          <td>
                            <small className="muted">
                              {m.last_login_at ? new Date(m.last_login_at).toLocaleDateString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'}
                            </small>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                              <button 
                                className="icon-button" 
                                title="View Profile Details"
                                onClick={() => setDetailModal(m)}
                              >
                                <Eye size={15}/>
                              </button>
                              
                              {(isCompanyAdmin || isManager) && (
                                <>
                                  {isCompanyAdmin && <button 
                                    className="icon-button" 
                                    title="Edit Role"
                                    onClick={() => setEditRoleModal(m)}
                                  >
                                    <Edit3 size={15}/>
                                  </button>}
                                  <button 
                                    className="icon-button danger-icon" 
                                    title="Remove from Organization"
                                    onClick={() => setRemoveConfirm(m)}
                                    style={{ color: '#ff7a95' }}
                                  >
                                    <Trash2 size={15}/>
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination footer */}
            {totalPages > 1 && (
              <div className="panel-head" style={{ borderTop: '1px solid #202737', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="muted" style={{ fontSize: '12px' }}>
                  Page {currentPage} of {totalPages}
                </span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button 
                    className="button secondary" 
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                    style={{ padding: '6px 12px' }}
                  >
                    <ChevronLeft size={14}/> Previous
                  </button>
                  <button 
                    className="button secondary" 
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                    style={{ padding: '6px 12px' }}
                  >
                    Next <ChevronRight size={14}/>
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* ─── MODALS ─── */}

      {/* 1. Invite Modal */}
      {inviteModal && (
        <InviteMemberModal 
          onClose={() => setInviteModal(false)} 
          onSuccess={() => {
            setInviteModal(false)
            loadMembers()
          }}
          managerMode={isManager}
        />
      )}

      {/* 2. Detail Modal */}
      {detailModal && (
        <MemberDetailModal 
          member={detailModal} 
          onClose={() => setDetailModal(null)} 
        />
      )}

      {/* 3. Edit Role Modal */}
      {editRoleModal && (
        <EditRoleModal 
          member={editRoleModal} 
          allMembers={members}
          onClose={() => setEditRoleModal(null)}
          onSave={(newRole, managerId) => handleUpdateRole(editRoleModal.id, newRole, managerId)}
        />
      )}

      {/* 4. Remove Member Confirmation Modal */}
      {removeConfirm && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="panel-head" style={{ padding: 0 }}>
              <h3 style={{ color: '#ff5978' }}>Remove Workspace Member?</h3>
              <button className="icon-button" onClick={() => setRemoveConfirm(null)}><X size={18}/></button>
            </div>
            <div style={{ marginTop: '12px' }}>
              <p className="muted" style={{ fontSize: '13px', lineHeight: '1.5' }}>
                Are you sure you want to remove <strong>{removeConfirm.name}</strong> ({removeConfirm.email}) from your organization?
              </p>
              <p className="muted" style={{ fontSize: '12px', marginTop: '8px', borderLeft: '3px solid #ff5978', paddingLeft: '10px' }}>
                This member will be detached from the company workspace and their role will be reset. All their reporting structures will be updated.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button secondary" onClick={() => setRemoveConfirm(null)}>Cancel</button>
              <button className="button primary" style={{ background: '#ff5978' }} onClick={() => handleRemove(removeConfirm.id)}>
                Confirm Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   SUBCOMPONENTS
   ───────────────────────────────────────────────────────────────────────────── */

// 1. Invite Member Modal Subcomponent
function InviteMemberModal({ onClose, onSuccess, managerMode = false }) {
  const { showToast } = useToast()
  const [form, setForm] = useState({ name: '', email: '', role: 'employee', manager_id: '' })
  const [loading, setLoading] = useState(false)
  const [managers, setManagers] = useState([])

  useEffect(() => {
    (managerMode ? organizationApi.teamMembers() : organizationApi.members())
      .then(r => setManagers(managerMode ? [] : r.data.filter(m => m.role === 'manager')))
      .catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.email.trim()) {
      showToast('error', 'Please fill in all required fields.')
      return
    }

    setLoading(true)
    try {
      const payload = {
        employee_name: form.name,
        employee_email: form.email,
        role: form.role,
        manager_id: form.manager_id ? Number(form.manager_id) : null
      }
      await invitationApi.send(payload)
      showToast('success', 'Invitation sent successfully!')
      onSuccess()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to send invitation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="panel-head" style={{ padding: 0 }}>
          <h3>{managerMode ? 'Invite Employee to My Team' : 'Invite Member to Workspace'}</h3>
          <button className="icon-button" onClick={onClose}><X size={18}/></button>
        </div>
        <form onSubmit={handleSubmit} style={{ marginTop: '16px' }}>
          <label className="field">
            <span>Full Name <span style={{ color: '#ff5978' }}>*</span></span>
            <input 
              required 
              placeholder="E.g., Jane Doe" 
              value={form.name} 
              onChange={e => setForm({ ...form, name: e.target.value })}
            />
          </label>

          <label className="field">
            <span>Email Address <span style={{ color: '#ff5978' }}>*</span></span>
            <input 
              type="email" 
              required 
              placeholder="E.g., jane@company.com" 
              value={form.email} 
              onChange={e => setForm({ ...form, email: e.target.value })}
            />
          </label>

          <label className="field">
            <span>Role <span style={{ color: '#ff5978' }}>*</span></span>
            <select 
              value={form.role} 
              onChange={e => setForm({ ...form, role: e.target.value })}
            >
              <option value="employee">Employee</option>
              {!managerMode && <option value="manager">Manager (Team Lead)</option>}
            </select>
          </label>

          {form.role === 'employee' && managers.length > 0 && (
            <label className="field">
              <span>Reporting Manager (Optional)</span>
              <select 
                value={form.manager_id} 
                onChange={e => setForm({ ...form, manager_id: e.target.value })}
              >
                <option value="">Directly reports to Company Admin</option>
                {managers.map(mgr => (
                  <option key={mgr.id} value={mgr.id}>{mgr.name} ({mgr.email})</option>
                ))}
              </select>
            </label>
          )}

          <div className="modal-actions">
            <button type="button" className="button secondary" onClick={onClose} disabled={loading}>Cancel</button>
            <button type="submit" className="button primary" disabled={loading}>
              {loading ? 'Sending invitation...' : 'Send Invitation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// 2. Member Detail Modal Subcomponent
function MemberDetailModal({ member, onClose }) {
  const initial = (member.name || 'U')[0].toUpperCase()

  return (
    <div className="modal-backdrop">
      <div className="modal" style={{ width: 'min(480px, calc(100% - 30px))' }}>
        <div className="panel-head" style={{ padding: 0 }}>
          <h3>Member Profile Details</h3>
          <button className="icon-button" onClick={onClose}><X size={18}/></button>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '20px 0 15px', gap: '12px' }}>
          <span className={`avatar large ${member.role === 'manager' ? 'manager' : ''}`} style={{ width: '64px', height: '64px', fontSize: '24px' }}>
            {member.avatar_url ? (
              <img 
                src={`${import.meta.env.VITE_API_URL || ''}${member.avatar_url}`} 
                alt="avatar" 
                style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
              />
            ) : initial}
          </span>
          <div style={{ textAlign: 'center' }}>
            <h4 style={{ margin: '0 0 4px', fontSize: '18px' }}>{member.name}</h4>
            <span className="muted" style={{ fontSize: '13px' }}>{member.email}</span>
          </div>
        </div>

        <div className="pd-divider" style={{ margin: '15px 0' }}/>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Workspace Role</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.role === 'manager' ? 'Team Lead (Manager)' : 'Employee'}
            </strong>
          </div>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Reporting Manager</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.manager_name || 'Directly reports to Company'}
            </strong>
          </div>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Department</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.department || '—'}
            </strong>
          </div>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Designation</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.designation || '—'}
            </strong>
          </div>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Member Since</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.created_at ? new Date(member.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'}
            </strong>
          </div>
          <div>
            <span className="muted" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase' }}>Last Login</span>
            <strong style={{ display: 'block', fontSize: '13px', marginTop: '3px' }}>
              {member.last_login_at ? new Date(member.last_login_at).toLocaleDateString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Never'}
            </strong>
          </div>
        </div>

        <div className="modal-actions" style={{ marginTop: '24px' }}>
          <button className="button secondary" onClick={onClose}>Close Details</button>
        </div>
      </div>
    </div>
  )
}

// 3. Edit Role Modal Subcomponent
function EditRoleModal({ member, allMembers, onClose, onSave }) {
  const [role, setRole] = useState(member.role || 'employee')
  const [managerId, setManagerId] = useState(member.manager_id || '')
  
  // Filter eligible managers (excluding the member being edited)
  const managers = useMemo(() => {
    return allMembers.filter(m => m.role === 'manager' && m.id !== member.id)
  }, [allMembers, member])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave(role, role === 'employee' && managerId ? Number(managerId) : null)
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="panel-head" style={{ padding: 0 }}>
          <h3>Edit Workspace Member Role</h3>
          <button className="icon-button" onClick={onClose}><X size={18}/></button>
        </div>
        <form onSubmit={handleSubmit} style={{ marginTop: '16px' }}>
          <div style={{ marginBottom: '14px' }}>
            <span className="muted" style={{ fontSize: '12px' }}>Editing Role For</span>
            <strong style={{ display: 'block', fontSize: '14px', marginTop: '3px' }}>{member.name} ({member.email})</strong>
          </div>

          <label className="field">
            <span>Role <span style={{ color: '#ff5978' }}>*</span></span>
            <select 
              value={role} 
              onChange={e => setRole(e.target.value)}
            >
              <option value="employee">Employee</option>
              <option value="manager">Manager (Team Lead)</option>
            </select>
          </label>

          {role === 'employee' && managers.length > 0 && (
            <label className="field">
              <span>Reporting Manager</span>
              <select 
                value={managerId} 
                onChange={e => setManagerId(e.target.value)}
              >
                <option value="">Directly reports to Company Admin</option>
                {managers.map(mgr => (
                  <option key={mgr.id} value={mgr.id}>{mgr.name} ({mgr.email})</option>
                ))}
              </select>
            </label>
          )}

          <div className="modal-actions">
            <button type="button" className="button secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="button primary">Save Role Changes</button>
          </div>
        </form>
      </div>
    </div>
  )
}
