import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '', timeout: 15000 })
api.interceptors.request.use(config => {
  const token = localStorage.getItem('tokenpilot_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (config.url?.includes('/messages') && config.data?.content && window.tokenpilotWorkspaceContext) {
    config.data = { ...config.data, content: `${config.data.content}\n\nWorkspace context:\n${window.tokenpilotWorkspaceContext}` }
  }
  if (config.url?.includes('/messages') && window.tokenpilotCacheReuse) { config.data = { ...config.data, ...window.tokenpilotCacheReuse }; window.tokenpilotCacheReuse = null }
  return config
})
api.interceptors.response.use(r => r, error => {
  if (error.response?.status === 409 && error.response?.data?.detail?.code === 'CACHE_CONFIRMATION_REQUIRED') window.dispatchEvent(new CustomEvent('tokenpilot:cache-candidate', { detail:error.response.data.detail.candidate }))
  if (error.response?.status === 401 && !error.config?.url?.includes('/auth/')) {
    window.dispatchEvent(new Event('tokenpilot:logout'))
  }
  return Promise.reject(error)
})

export const authApi = {
  companyRegister: p => api.post('/auth/company/register', p), companyVerify: p => api.post('/auth/company/verify-otp', p), companyLogin: p => api.post('/auth/company/login', p),
  employeeRegister: p => api.post('/auth/employee/register', p), employeeVerify: p => api.post('/auth/employee/verify-otp', p), employeeLogin: p => api.post('/auth/employee/login', p),
  forgot: (kind, p) => api.post(`/auth/${kind}/forgot-password`, p), reset: (kind, p) => api.post(`/auth/${kind}/reset-password`, p)
}
export const dashboardApi = { company: () => api.get('/dashboard/company'), manager: () => api.get('/dashboard/team-lead'), employee: () => api.get('/dashboard/employee'), optimization: () => api.get('/workspace/optimization/analytics') }
export const apiKeyRequestApi = {
  create: payload => api.post('/api/requests', payload),
  mine: () => api.get('/api/requests/my'),
  teamLeader: () => api.get('/api/teamleader/requests'),
  teamLeaderAction: (id, payload) => api.patch(`/api/teamleader/requests/${id}`, payload),
  companyRequests: () => api.get('/api/company/api-key-requests'),
  companyAction: (id, payload) => api.patch(`/api/company/api-key-requests/${id}`, payload),
  createKey: payload => api.post('/api/company/api-keys', payload),
  companyKeys: () => api.get('/api/company/api-keys')
}
export const workspaceApi = {
  connection: () => api.get('/workspace/connection'), connections: () => api.get('/workspace/connections'), personalKeys: () => api.get('/workspace/personal-keys'), personalKey: p => api.post('/workspace/personal-key', p), updatePersonalKey: (id, p) => api.patch(`/workspace/personal-keys/${id}`, p), deletePersonalKey: id => api.delete(`/workspace/personal-keys/${id}`),
  chats: q => api.get('/workspace/chats', { params: q ? { q } : {} }), createChat: () => api.post('/workspace/chats'), chat: id => api.get(`/workspace/chats/${id}`), renameChat: (id, p) => api.patch(`/workspace/chats/${id}`, p), deleteChat: id => api.delete(`/workspace/chats/${id}`), sendNew: p => api.post('/workspace/chats/messages', p, { timeout: 180000 }), send: (id, p) => api.post(`/workspace/chats/${id}/messages`, p, { timeout: 180000 }),
  files: () => api.get('/workspace/files'), createFile: p => api.post('/workspace/files', p), updateFile: (id, p) => api.patch(`/workspace/files/${id}`, p), deleteFile: id => api.delete(`/workspace/files/${id}`), optimizationSettings: () => api.get('/workspace/optimization/settings'), updateOptimizationSettings: p => api.patch('/workspace/optimization/settings', p), optimizationAnalytics: () => api.get('/workspace/optimization/analytics')
}
export const organizationApi = {
  tree: () => api.get('/organization/tree'),
  me: () => api.get('/organization/me'),
  subordinates: () => api.get('/organization/subordinates'),
  all: () => api.get('/organization/employees'),
  promote: (id, p) => api.post(`/organization/employees/${id}/promote`, p),
  demote: id => api.post(`/organization/employees/${id}/demote`),
  manager: (id, p) => api.patch(`/organization/employees/${id}/manager`, p),
  members: () => api.get('/organization/members'),
  teamMembers: () => api.get('/organization/team-members'),
  memberDetail: id => api.get(`/organization/members/${id}`),
  teamMemberDetail: id => api.get(`/organization/team-members/${id}`),
  updateRole: (id, p) => api.patch(`/organization/members/${id}/role`, p),
  removeMember: id => api.delete(`/organization/members/${id}`),
  removeTeamMember: id => api.delete(`/organization/team-members/${id}`)
}
export const budgetApi = { company: () => api.get('/token-budgets/company'), team: () => api.get('/token-budgets/team'), me: () => api.get('/token-budgets/me'), create: p => api.post('/token-budgets', p), update: (id, p) => api.patch(`/token-budgets/${id}`, p), teamUpdate: (id, p) => api.patch(`/token-budgets/team/${id}`, p), reset: () => api.post('/token-budgets/reset') }
export const invitationApi = {
  send: p => api.post('/invitations/send', p),
  list: () => api.get('/invitations/list'),
  team: () => api.get('/invitations/team'),
  mine: () => api.get('/invitations/mine'),
  resend: id => api.post(`/invitations/${id}/resend`),
  cancel: id => api.post(`/invitations/${id}/cancel`),
  delete: id => api.delete(`/invitations/${id}`),
  verify: token => api.get(`/invitations/verify/${token}`),
  accept: p => api.post('/invitations/accept', p),
  reject: p => api.post('/invitations/reject', p)
}
export const notificationApi = { list: (params = {}) => api.get('/notifications', { params }), read: id => api.patch(`/notifications/${id}/read`), readAll: () => api.post('/notifications/read-all') }
export const profileApi = { get: () => api.get('/profile'), update: p => api.patch('/profile', p), uploadAvatar: f => { const fd = new FormData(); fd.append('file', f); return api.post('/profile/avatar', fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, deleteAvatar: () => api.delete('/profile/avatar') }
export const settingsApi = { changePassword: p => api.post('/settings/change-password/request', p), changePasswordVerify: p => api.post('/settings/change-password/verify', p) }
export const securityApi = { info: () => api.get('/security/info') }
export const supportApi = { reportBug: (category, subject, description, screenshot) => { const fd = new FormData(); fd.append('category', category); fd.append('subject', subject); fd.append('description', description); if (screenshot) fd.append('screenshot', screenshot); return api.post('/support/report-bug', fd, { headers: { 'Content-Type': 'multipart/form-data' } }) } }
