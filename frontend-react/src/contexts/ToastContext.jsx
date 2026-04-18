import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)
let _nextId = 1

const typeMap = {
  success: {
    bg: 'linear-gradient(135deg, #10b981, #059669)',
    icon: '✓',
  },
  error: {
    bg: 'linear-gradient(135deg, #ef4444, #dc2626)',
    icon: '✗',
  },
  info: {
    bg: 'linear-gradient(135deg, #6366f1, #4f46e5)',
    icon: 'ℹ',
  },
  warning: {
    bg: 'linear-gradient(135deg, #f59e0b, #d97706)',
    icon: '⚠',
  },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = _nextId++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div style={{
        position: 'fixed', top: '20px', right: '20px', zIndex: 99999,
        display: 'flex', flexDirection: 'column', gap: '10px',
        pointerEvents: 'none',
        maxWidth: '340px',
      }}>
        {toasts.map(t => {
          const cfg = typeMap[t.type] || typeMap.info
          return (
            <div key={t.id} style={{
              pointerEvents: 'auto',
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '12px 16px',
              background: cfg.bg,
              borderRadius: '12px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
              color: 'white',
              fontSize: '13px',
              fontWeight: '500',
              animation: 'fadeSlideUp 0.25s cubic-bezier(0.4,0,0.2,1) both',
              backdropFilter: 'blur(8px)',
            }}>
              <span style={{
                width: '20px', height: '20px', borderRadius: '50%',
                background: 'rgba(255,255,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '11px', fontWeight: '700', flexShrink: 0,
              }}>
                {cfg.icon}
              </span>
              <span style={{ flex: 1 }}>{t.message}</span>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

let _addToast = null
export function setToastAdder(fn) { _addToast = fn }
export function toast(msg, type = 'info') { _addToast?.(msg, type) }
