import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)

  const showToast = useCallback((type, text) => {
    // FastAPI validation errors return `detail` as an array of objects.
    // React cannot render those objects directly as children.
    const normalizedText = Array.isArray(text)
      ? text.map(item => item?.msg || item?.message || String(item)).join(', ')
      : text && typeof text === 'object'
        ? text.message || text.msg || JSON.stringify(text)
        : String(text ?? '')
    setToast({ type, text: normalizedText })
  }, [])

  const hideToast = useCallback(() => {
    setToast(null)
  }, [])

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        setToast(null)
      }, 4000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  return (
    <ToastContext.Provider value={{ showToast, hideToast }}>
      {children}
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>
            <span>{toast.text}</span>
            <button type="button" className="toast-close" onClick={hideToast}>×</button>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

export const useToast = () => {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
