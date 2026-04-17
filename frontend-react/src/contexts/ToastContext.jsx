import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)

let _nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 3500) => {
    const id = _nextId++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed top-14 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id}
            className={`pointer-events-auto px-4 py-2.5 rounded-md text-sm font-medium shadow-lg
              ${t.type === 'success' ? 'bg-emerald-800 text-emerald-200 border border-emerald-700' : ''}
              ${t.type === 'error' ? 'bg-red-900 text-red-200 border border-red-800' : ''}
              ${t.type === 'info' ? 'bg-slate-800 text-slate-200 border border-slate-700' : ''}
              ${t.type === 'warning' ? 'bg-amber-900 text-amber-200 border border-amber-800' : ''}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

// Singleton for non-React code
let _addToast = null
export function setToastAdder(fn) { _addToast = fn }
export function toast(msg, type = 'info') { _addToast?.(msg, type) }
