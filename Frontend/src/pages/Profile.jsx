import { useEffect, useRef, useState } from 'react'
import { Camera, Save, X, Trash2, UploadCloud, RefreshCw } from 'lucide-react'
import { profileApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import { useAuth } from '../contexts/AuthContext'
import Loading from '../components/Loading'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function Profile() {
  const { showToast } = useToast()
  const { fetchAuthProfile, user: authUser } = useAuth()
  const { fetchProfile } = useAuth()
  const [data, setData] = useState(null)
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [avatarLoading, setAvatarLoading] = useState(false)
  
  // Drag & drop state
  const [dragActive, setDragActive] = useState(false)
  const fileRef = useRef()

  const load = async () => {
    try {
      const r = await profileApi.get()
      setData(r.data)
      setForm({
        name: r.data.name || '',
        phone: r.data.phone || '',
        address: r.data.address || '',
        city: r.data.city || '',
        state: r.data.state || '',
        country: r.data.country || '',
        postal_code: r.data.postal_code || '',
        website: r.data.website || '',
        industry: r.data.industry || '',
        company_size: r.data.company_size || '',
        department: r.data.department || '',
        designation: r.data.designation || '',
      })
    } catch { showToast('error', 'Failed to load profile.') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleUpload = async (file) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/jpg'].includes(file.type)) {
      showToast('error', 'Only JPG and PNG images are allowed.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast('error', 'Image must be under 5 MB.')
      return
    }
    
    setAvatarLoading(true)
    try {
      await profileApi.uploadAvatar(file)
      showToast('success', 'Profile photo updated.')
      // Refresh auth profile globally so it updates everywhere instantly
      await fetchProfile(authUser?.type)
      await load()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to upload photo.')
    } finally {
      setAvatarLoading(false)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    handleUpload(file)
  }

  const handleRemovePhoto = async () => {
    if (window.confirm('Are you sure you want to remove your profile photo?')) {
      setAvatarLoading(true)
      try {
        await profileApi.deleteAvatar()
        showToast('success', 'Profile photo removed.')
        await fetchProfile(authUser?.type)
        await load()
      } catch (err) {
        showToast('error', err.response?.data?.detail || 'Failed to remove photo.')
      } finally {
        setAvatarLoading(false)
      }
    }
  }

  // Drag & drop handlers
  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0])
    }
  }

  const handleSaveInfo = async () => {
    setSaving(true)
    try {
      const payload = { ...form }
      if (data.role === 'Company Admin') {
        delete payload.department; delete payload.designation
      } else {
        delete payload.website; delete payload.industry; delete payload.company_size
      }
      await profileApi.update(payload)
      showToast('success', 'Profile updated successfully.')
      await fetchProfile(authUser?.type)
      load()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to update profile.')
    } finally { setSaving(false) }
  }

  const handleCancel = () => {
    if (data) {
      setForm({
        name: data.name || '', phone: data.phone || '', address: data.address || '',
        city: data.city || '', state: data.state || '', country: data.country || '',
        postal_code: data.postal_code || '', website: data.website || '',
        industry: data.industry || '', company_size: data.company_size || '',
        department: data.department || '', designation: data.designation || '',
      })
    }
  }

  const set = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  if (loading) return <Loading/>

  const avatarSrc = data?.avatar_url ? `${API_BASE}${data.avatar_url}` : null
  const initial = (data?.name || 'U')[0].toUpperCase()
  const isCompany = data?.role === 'Company Admin'

  return (
    <div className="profile-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ACCOUNT</div>
          <h1>Profile</h1>
          <p className="muted">Manage your personal information and workspace details.</p>
        </div>
      </div>

      <div className="profile-layout">
        {/* Modern SaaS Profile Photo Card */}
        <div 
          className={`panel profile-avatar-card ${dragActive ? 'drag-active' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          style={{
            position: 'relative',
            border: dragActive ? '2px dashed #8b5cf6' : '1px solid #20283a',
            transition: 'all 0.2s ease',
            background: dragActive ? 'rgba(139, 92, 246, 0.05)' : 'linear-gradient(145deg,#141925,#11141d)'
          }}
        >
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            <div className="avatar-upload-area" onClick={() => fileRef.current.click()} style={{ width: '110px', height: '110px' }}>
              {avatarSrc
                ? <img src={avatarSrc} alt="avatar" className="avatar-img-preview" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}/>
                : <div className="avatar large" style={{ width: '100%', height: '100%', borderRadius: '50%', fontSize: '36px' }}>{initial}</div>
              }
              
              <div className="avatar-overlay" style={{ borderRadius: '50%' }}>
                <Camera size={22}/>
                <span>Change Photo</span>
              </div>
              
              {avatarLoading && (
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'rgba(11, 13, 19, 0.8)',
                  display: 'grid',
                  placeItems: 'center',
                  borderRadius: '50%',
                  zIndex: 5
                }}>
                  <RefreshCw size={24} className="spinner" style={{ color: '#8b5cf6' }}/>
                </div>
              )}
            </div>

            <div className="avatar-card-info" style={{ width: '100%', textAlign: 'center' }}>
              <strong style={{ fontSize: '18px', display: 'block', marginBottom: '4px' }}>{data?.name}</strong>
              <span className="muted" style={{ fontSize: '13px', display: 'block', marginBottom: '8px' }}>{data?.role}</span>
              
              {!avatarSrc ? (
                <p className="muted" style={{ fontSize: '12px', margin: '4px 0 12px' }}>
                  No profile photo uploaded.
                </p>
              ) : null}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
              <button 
                type="button" 
                className="button primary full" 
                onClick={() => fileRef.current.click()} 
                disabled={avatarLoading}
                style={{ height: '38px' }}
              >
                <UploadCloud size={15}/> {avatarSrc ? 'Replace Photo' : 'Upload Photo'}
              </button>
              
              {avatarSrc && (
                <button 
                  type="button" 
                  className="button secondary full danger-icon" 
                  onClick={handleRemovePhoto} 
                  disabled={avatarLoading}
                  style={{ height: '38px', borderColor: 'rgba(255, 89, 120, 0.2)', color: '#ff7a95' }}
                >
                  <Trash2 size={15}/> Remove Photo
                </button>
              )}
            </div>

            <div className="muted" style={{ fontSize: '11px', textAlign: 'center', marginTop: '4px', lineHeight: '1.4' }}>
              Drag and drop image here. JPG, PNG up to 5MB.
            </div>
          </div>
          
          <input ref={fileRef} type="file" accept="image/jpeg,image/png" style={{ display: 'none' }} onChange={handleFileChange}/>
        </div>

        {/* Form card */}
        <div className="panel profile-form-card">
          <h3>Personal Information</h3>

          <div className="form-grid">
            <PField label="Full Name" name="name" value={form.name} onChange={set}/>
            <PField label="Phone Number" name="phone" value={form.phone} onChange={set}/>
            <PField label="Address" name="address" value={form.address} onChange={set} full/>
            <PField label="City" name="city" value={form.city} onChange={set}/>
            <PField label="State / Province" name="state" value={form.state} onChange={set}/>
            <PField label="Country" name="country" value={form.country} onChange={set}/>
            <PField label="Postal Code" name="postal_code" value={form.postal_code} onChange={set}/>
          </div>

          <h3 className="section-divider">Account Details</h3>
          <div className="form-grid">
            <PFieldReadOnly label="Email" value={data?.email}/>
            <PFieldReadOnly label="Company" value={data?.company_name}/>
            <PFieldReadOnly label="Role" value={data?.role}/>
          </div>

          {!isCompany && (
            <>
              <h3 className="section-divider">Work Information</h3>
              <div className="form-grid">
                <PField label="Department" name="department" value={form.department} onChange={set}/>
                <PField label="Designation" name="designation" value={form.designation} onChange={set}/>
                <PFieldReadOnly label="Reporting Manager" value={data?.reporting_manager || '—'}/>
              </div>
            </>
          )}

          {isCompany && (
            <>
              <h3 className="section-divider">Company Information</h3>
              <div className="form-grid">
                <PField label="Website" name="website" value={form.website} onChange={set}/>
                <PField label="Industry" name="industry" value={form.industry} onChange={set}/>
                <PField label="Company Size" name="company_size" value={form.company_size} onChange={set}/>
              </div>
            </>
          )}

          <div className="form-actions">
            <button className="button secondary" onClick={handleCancel} disabled={saving}>
              <X size={15}/> Cancel
            </button>
            <button className="button primary" onClick={handleSaveInfo} disabled={saving}>
              <Save size={15}/> {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PField({ label, name, value, onChange, full }) {
  return (
    <label className={`field${full ? ' full-width' : ''}`}>
      <span>{label}</span>
      <input name={name} value={value} onChange={onChange} autoComplete="off"/>
    </label>
  )
}

function PFieldReadOnly({ label, value }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value || ''} readOnly className="readonly"/>
    </label>
  )
}
