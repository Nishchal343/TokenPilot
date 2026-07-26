import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '', timeout: 15000 })
api.interceptors.request.use(config => {
  const token = localStorage.getItem('tokenpilot_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(r => r, error => {
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
export const dashboardApi = { company: () => api.get('/dashboard/company'), manager: () => api.get('/dashboard/team-lead'), employee: () => api.get('/dashboard/employee') }
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
