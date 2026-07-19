import { useRef, useState } from 'react'
import { Bug, Paperclip, Send, X } from 'lucide-react'
import { supportApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'

const CATEGORIES = ['ui', 'backend', 'security', 'performance', 'other']

export default function BugReportModal({ onClose }) {
  const { showToast } = useToast()
  const [form, setForm] = useState({ category: 'ui', subject: '', description: '' })
  const [screenshot, setScreenshot] = useState(null)
  const [loading, setLoading] = useState(false)
  const fileRef = useRef()

  const set = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleFile = e => {
    const file = e.target.files[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { showToast('error', 'Screenshot must be under 10 MB.'); return }
    setScreenshot(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.subject.trim() || !form.description.trim()) {
      showToast('error', 'Please fill in all required fields.')
      return
    }
    setLoading(true)
    try {
      await supportApi.reportBug(form.category, form.subject, form.description, screenshot)
      showToast('success', 'Bug report submitted. Thank you!')
      onClose()
    } catch (err) {
      showToast('error', err.response?.data?.detail || 'Failed to submit report.')
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-box bug-modal">
        <div className="modal-head">
          <div className="modal-title"><Bug size={18}/> Report a Bug</div>
          <button className="icon-button" onClick={onClose}><X size={18}/></button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <label className="field">
            <span>Category</span>
            <select name="category" value={form.category} onChange={set}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
            </select>
          </label>

          <label className="field">
            <span>Subject <span className="required">*</span></span>
            <input name="subject" value={form.subject} onChange={set} placeholder="Brief summary of the issue" required/>
          </label>

          <label className="field">
            <span>Description <span className="required">*</span></span>
            <textarea name="description" value={form.description} onChange={set} placeholder="Describe the bug in detail: steps to reproduce, expected vs actual behavior…" rows={5} required/>
          </label>

          <div className="screenshot-row">
            <button type="button" className="button secondary" onClick={() => fileRef.current.click()}>
              <Paperclip size={14}/> {screenshot ? screenshot.name : 'Attach Screenshot (optional)'}
            </button>
            {screenshot && <button type="button" className="icon-button" onClick={() => setScreenshot(null)}><X size={13}/></button>}
            <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFile}/>
          </div>

          <div className="modal-footer">
            <button type="button" className="button ghost" onClick={onClose} disabled={loading}>Cancel</button>
            <button type="submit" className="button primary" disabled={loading}>
              <Send size={14}/> {loading ? 'Submitting…' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
