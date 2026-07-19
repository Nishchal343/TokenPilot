import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)

  const showToast = useCallback((type, text) => {
    setToast({ type, text })
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
