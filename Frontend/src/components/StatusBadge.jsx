const STATUS_META = {
  pending: { className: 'pending', label: 'Pending Approval' },
  approved: { className: 'approved', label: 'Approved' },
  rejected: { className: 'rejected', label: 'Rejected' }
}

function getStatusMeta(status) {
  const value = String(status || '').toLowerCase()
  if (value.includes('reject') || value === 'cancelled') return STATUS_META.rejected
  if (value.includes('approv') || value === 'accepted') return STATUS_META.approved
  if (value.includes('pending') || value === 'expired') return STATUS_META.pending
  return { className: 'neutral', label: status || 'Unknown' }
}

export default function StatusBadge({ status }) {
  const meta = getStatusMeta(status)
  return <span className={`status-badge status-badge-${meta.className}`}><i aria-hidden="true" />{meta.label}</span>
}
