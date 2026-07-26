import { useEffect, useState, useMemo } from 'react'
import { 
  ChevronLeft, 
  ChevronRight, 
  Search, 
  UserPlus, 
  Mail, 
  Trash2, 
  XCircle, 
  RefreshCw, 
  AlertCircle,
  X
} from 'lucide-react'
import { invitationApi, organizationApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import Loading from '../components/Loading'
import StatusBadge from '../components/StatusBadge'

export default function Invitations() {
  const { user } = useAuth()
  const { showToast } = useToast()

  const [invites, setInvites] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters & layout state
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  // Modal actions
  const [inviteModal, setInviteModal] = useState(false)
  const [cancelConfirm, setCancelConfirm] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  const isCompanyAdmin = user?.type === 'company'

  const loadInvitations = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await invitationApi.list()
      setInvites(response.data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to load invitations.')
      showToast('error', 'Failed to load invitations.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isCompanyAdmin) {
      loadInvitations()
    } else {
      setLoading(false)
    }
  }, [isCompanyAdmin])

  // Filter & Search
  const filteredInvites = useMemo(() => {
    if (!invites) return []

    let result = invites.filter(item => 
      (item.name && item.name.toLowerCase().includes(query.toLowerCase())) ||
      item.email.toLowerCase().includes(query.toLowerCase())
    )

    if (statusFilter !== 'all') {
      result = result.filter(item => item.status === statusFilter)
    }

    return result
  }, [invites, query, statusFilter])

  // Pagination
  const paginatedInvites = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return filteredInvites.slice(start, start + itemsPerPage)
  }, [filteredInvites, currentPage])

  const totalPages = Math.ceil(filteredInvites.length / itemsPerPage) || 1

  useEffect(() => {
    setCurrentPage(1)
  }, [query, statusFilter])

  const handleResend = async (inviteId) => {
    setActionLoading(true)
    try {
      await invitationApi.resend(inviteId)
      showToast('success', 'Invitation resent successfully!')
      loadInvitations()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to resend invitation.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async (inviteId) => {
    setActionLoading(true)
    try {
      await invitationApi.cancel(inviteId)
      showToast('success', 'Invitation cancelled successfully.')
      setCancelConfirm(null)
      loadInvitations()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to cancel invitation.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async (inviteId) => {
    setActionLoading(true)
    try {
      await invitationApi.delete(inviteId)
      showToast('success', 'Invitation record deleted.')
      setDeleteConfirm(null)
      loadInvitations()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to delete invitation record.')
    } finally {
      setActionLoading(false)
    }
  }

  if (!isCompanyAdmin) {
    return (
      <div className="dashboard">
        <div className="empty-state">
          <AlertCircle size={32} className="muted" />
          <h3>Access Denied</h3>
          <p>Only Company Admins can manage organization invitations.</p>
        </div>
      </div>
    )
  }

  if (loading && !invites) return <Loading />

  return (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <div className="eyebrow">INBOX</div>
          <h1>Workspace Invitations</h1>
          <p className="muted">Track and manage invitations offered to onboarding or existing team members.</p>
        </div>
        <button className="button primary" onClick={() => setInviteModal(true)}>
          <UserPlus size={16}/> Invite Member
        </button>
      </div>

      {error ? (
        <div className="empty-state">
          <AlertCircle size={32} className="muted" style={{ color: '#ff5978' }}/>
          <h3>Error Loading Invitations</h3>
          <p>{error}</p>
          <button className="button secondary" onClick={loadInvitations} style={{ marginTop: '12px' }}>
            Retry
          </button>
        </div>
      ) : (
        <>
          {/* Status filter buttons/tabs */}
          <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #202737', paddingBottom: '12px', marginBottom: '20px', overflowX: 'auto' }}>
            {['all', 'pending', 'accepted', 'rejected'].map(status => {
              const count = invites ? invites.filter(item => status === 'all' || item.status === status).length : 0
              return (
                <button
                  key={status}
                  className={`button secondary ${statusFilter === status ? 'active' : ''}`}
                  onClick={() => setStatusFilter(status)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    background: statusFilter === status ? 'rgba(139, 92, 246, 0.15)' : '#141925',
                    borderColor: statusFilter === status ? '#8b5cf6' : '#252d3e',
                    color: statusFilter === status ? '#fff' : '#a5afc2'
                  }}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)} ({count})
                </button>
              )
            })}
          </div>

          {/* Search Toolbar */}
          <div className="toolbar" style={{ marginBottom: '20px' }}>
            <div className="search wide" style={{ width: '100%' }}>
              <Search size={16}/>
              <input 
                placeholder="Search by invitee name or email..." 
                value={query} 
                onChange={e => setQuery(e.target.value)}
              />
            </div>
          </div>

          {/* Table list */}
          <div className="panel table-panel">
            <div className="panel-head">
              <h3>Invitation Records</h3>
              <span className="muted">{filteredInvites.length} {filteredInvites.length === 1 ? 'invitation' : 'invitations'} total</span>
            </div>

            {loading ? (
              <div className="loading" style={{ minHeight: '200px' }}>
                <span className="spinner"></span> Loading invitation data...
              </div>
            ) : paginatedInvites.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon"><Mail size={20}/></div>
                <h3>No invitations found</h3>
                <p>No invitation records match the chosen status filter or search parameters.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Invitee Name</th>
                      <th>Email</th>
                      <th>Offered Role</th>
                      <th>Status</th>
                      <th>Sent Date</th>
                      <th>Expiry Date</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedInvites.map(item => {
                      return (
                        <tr key={item.id}>
                          <td><b>{item.name || '—'}</b></td>
                          <td><span className="muted">{item.email}</span></td>
                          <td>
                            {item.role_offered === 'manager' ? (
                              <span className="role-chip" style={{ color: '#c4b5fd', background: 'rgba(139, 92, 246, 0.12)', borderColor: 'rgba(139, 92, 246, 0.3)' }}>Manager</span>
                            ) : (
                              <span className="role-chip" style={{ color: '#a5afc2', background: 'rgba(41, 50, 71, 0.15)', borderColor: 'rgba(41, 50, 71, 0.4)' }}>Employee</span>
                            )}
                          </td>
                          <td>
                            <StatusBadge status={item.status}/>
                          </td>
                          <td>
                            <small className="muted">
                              {item.created_at ? new Date(item.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'}
                            </small>
                          </td>
                          <td>
                            <small className="muted">
                              {item.token_expires_at ? new Date(item.token_expires_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'}
                            </small>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                              {(item.status === 'pending' || item.status === 'expired') && (
                                <button 
                                  className="icon-button" 
                                  title="Resend Invitation Email"
                                  onClick={() => handleResend(item.id)}
                                  disabled={actionLoading}
                                >
                                  <RefreshCw size={15} className={actionLoading ? 'spinner' : ''}/>
                                </button>
                              )}
                              
                              {item.status === 'pending' && (
                                <button 
                                  className="icon-button danger-icon" 
                                  title="Cancel Invitation"
                                  onClick={() => setCancelConfirm(item)}
                                  disabled={actionLoading}
                                >
                                  <XCircle size={15}/>
                                </button>
                              )}

                              <button 
                                className="icon-button danger-icon" 
                                title="Delete Invitation Record"
                                onClick={() => setDeleteConfirm(item)}
                                disabled={actionLoading}
                                style={{ color: '#ff7a95' }}
                              >
                                <Trash2 size={15}/>
                              </button>
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
            loadInvitations()
          }}
        />
      )}

      {/* 2. Cancel Confirmation Modal */}
      {cancelConfirm && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="panel-head" style={{ padding: 0 }}>
              <h3 style={{ color: '#ff5978' }}>Cancel Invitation?</h3>
              <button className="icon-button" onClick={() => setCancelConfirm(null)}><X size={18}/></button>
            </div>
            <div style={{ marginTop: '12px' }}>
              <p className="muted" style={{ fontSize: '13px', lineHeight: '1.5' }}>
                Are you sure you want to cancel the pending invitation to <strong>{cancelConfirm.name || cancelConfirm.email}</strong>?
              </p>
              <p className="muted" style={{ fontSize: '12px', marginTop: '8px' }}>
                The link sent to their email will immediately stop working and they won't be able to register using this invitation.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button secondary" onClick={() => setCancelConfirm(null)} disabled={actionLoading}>Cancel</button>
              <button className="button primary" style={{ background: '#ff5978' }} onClick={() => handleCancel(cancelConfirm.id)} disabled={actionLoading}>
                {actionLoading ? 'Cancelling...' : 'Confirm Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="panel-head" style={{ padding: 0 }}>
              <h3 style={{ color: '#ff5978' }}>Delete Invitation Record?</h3>
              <button className="icon-button" onClick={() => setDeleteConfirm(null)}><X size={18}/></button>
            </div>
            <div style={{ marginTop: '12px' }}>
              <p className="muted" style={{ fontSize: '13px', lineHeight: '1.5' }}>
                Are you sure you want to permanently delete the invitation record for <strong>{deleteConfirm.name || deleteConfirm.email}</strong>?
              </p>
              <p className="muted" style={{ fontSize: '12px', marginTop: '8px', borderLeft: '3px solid #ff5978', paddingLeft: '10px' }}>
                This is a permanent deletion of this record from history database. If it is currently pending, deleting it will invalidate the link.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button secondary" onClick={() => setDeleteConfirm(null)} disabled={actionLoading}>Cancel</button>
              <button className="button primary" style={{ background: '#ff5978' }} onClick={() => handleDelete(deleteConfirm.id)} disabled={actionLoading}>
                {actionLoading ? 'Deleting...' : 'Delete Record'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   REUSED MODAL SUBCOMPONENT (Same as Organization.jsx to prevent duplicate structures)
   ───────────────────────────────────────────────────────────────────────────── */

function InviteMemberModal({ onClose, onSuccess }) {
  const { showToast } = useToast()
  const [form, setForm] = useState({ name: '', email: '', role: 'employee', manager_id: '' })
  const [loading, setLoading] = useState(false)
  const [managers, setManagers] = useState([])

  useEffect(() => {
    organizationApi.members()
      .then(r => setManagers(r.data.filter(m => m.role === 'manager')))
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
          <h3>Invite Member to Workspace</h3>
          <button type="button" className="icon-button" onClick={onClose}><X size={18}/></button>
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
              <option value="manager">Manager (Team Lead)</option>
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
