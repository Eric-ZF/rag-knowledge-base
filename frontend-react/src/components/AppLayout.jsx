import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'
import FolderTree from './left/FolderTree.jsx'
import UploadZone from './left/UploadZone.jsx'
import PaperList from './left/PaperList.jsx'
import QuotaBanner from './right/QuotaBanner.jsx'
import ChatPanel from './right/ChatPanel.jsx'
import ChatInput from './right/ChatInput.jsx'
import { Sun, Moon, Menu, X } from 'lucide-react'

function DarkToggle() {
  const [dark, setDark] = useState(() =>
    localStorage.getItem('theme') === 'dark' ||
    (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
  )

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [dark])

  return (
    <button
      onClick={() => setDark(d => !d)}
      style={{
        width: '32px', height: '32px', borderRadius: '9px',
        background: dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
        border: '1px solid var(--c-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'all 0.2s',
        flexShrink: 0,
      }}
      title={dark ? '切换亮色模式' : '切换深色模式'}
      onMouseOver={e => { e.currentTarget.style.background = 'var(--c-accent-soft)'; e.currentTarget.style.borderColor = 'var(--c-accent)' }}
      onMouseOut={e => { e.currentTarget.style.background = dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)'; e.currentTarget.style.borderColor = 'var(--c-border)' }}
    >
      {dark
        ? <Sun size={15} style={{ color: '#f59e0b' }} />
        : <Moon size={15} style={{ color: '#6366f1' }} />
      }
    </button>
  )
}

function MobileSidebar({ open, onClose, children }) {
  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 40,
            background: 'rgba(0,0,0,0.4)',
            backdropFilter: 'blur(4px)',
            animation: 'fadeIn 0.2s ease both',
          }}
        />
      )}
      {/* Drawer */}
      <div style={{
        position: 'fixed', left: 0, top: 0, bottom: 0, zIndex: 50,
        width: 'min(360px, 88vw)',
        background: 'var(--c-surface)',
        borderRight: '1px solid var(--c-border)',
        boxShadow: '4px 0 24px rgba(0,0,0,0.15)',
        transform: open ? 'translateX(0)' : 'translateX(-110%)',
        transition: 'transform 0.3s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {children}
      </div>
    </>
  )
}

export default function MainLayout() {
  const { userPhone, logout } = useAuth()
  const [currentFolderId, setCurrentFolderId] = useState(null)
  const [leftOpen, setLeftOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <div style={{
      animation: 'scaleIn 0.4s cubic-bezier(0.4,0,0.2,1) both',
      display: 'flex', flexDirection: 'column',
      height: '100vh', overflow: 'hidden',
      background: 'var(--c-bg)',
    }}>
      {/* Header */}
      <header style={{
        height: '56px', display: 'flex', alignItems: 'center',
        padding: '0 16px', gap: '12px', shrink: 0,
        background: 'var(--c-surface)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--c-border)',
        position: 'relative', zIndex: 10,
      }}>
        {isMobile && (
          <button
            onClick={() => setLeftOpen(true)}
            style={{
              width: '32px', height: '32px', borderRadius: '9px',
              background: 'transparent', border: '1px solid var(--c-border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', flexShrink: 0,
            }}
          >
            <Menu size={16} style={{ color: 'var(--c-text)' }} />
          </button>
        )}

        {/* Logo */}
        <div style={{
          width: '32px', height: '32px', borderRadius: '10px',
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '16px', boxShadow: '0 2px 8px rgba(102,126,234,0.3)',
          flexShrink: 0,
        }}>
          📚
        </div>
        <h1 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--c-text)' }}>
          RAG 学术知识库
        </h1>
        <span className="badge badge-accent" style={{ fontSize: '11px' }}>
          Phase 0
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <DarkToggle />
          <span style={{ fontSize: '13px', color: 'var(--c-muted)' }}>{userPhone}</span>
          <button
            onClick={logout}
            style={{
              fontSize: '12px', color: 'var(--c-muted)', cursor: 'pointer',
              background: 'none', border: 'none', padding: '4px 8px',
              borderRadius: '8px', transition: 'all 0.15s',
            }}
            onMouseOver={e => e.target.style.color = '#ef4444'}
            onMouseOut={e => e.target.style.color = 'var(--c-muted)'}
          >
            退出
          </button>
        </div>
      </header>

      {/* Desktop: side-by-side | Mobile: full-width chat with sidebar drawer */}
      {isMobile ? (
        /* Mobile: full-width Chat */
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <QuotaBanner />
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <ChatPanel folderIds={currentFolderId ? [currentFolderId] : []} />
            <ChatInput />
          </div>
          {/* Mobile sidebar */}
          <MobileSidebar open={leftOpen} onClose={() => setLeftOpen(false)}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', borderBottom: '1px solid var(--c-border)',
            }}>
              <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--c-text)' }}>论文管理</span>
              <button
                onClick={() => setLeftOpen(false)}
                style={{
                  width: '28px', height: '28px', borderRadius: '8px',
                  background: 'transparent', border: '1px solid var(--c-border)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer',
                }}
              >
                <X size={14} style={{ color: 'var(--c-text)' }} />
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <FolderTree onSelectFolder={id => { setCurrentFolderId(id); setLeftOpen(false) }} />
              <UploadZone folderId={currentFolderId} />
              <PaperList folderId={currentFolderId} />
            </div>
          </MobileSidebar>
        </div>
      ) : (
        /* Desktop: 50/50 split */
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Left panel */}
          <div style={{
            width: '50%', display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
            borderRight: '1px solid var(--c-border)',
            background: 'rgba(var(--c-surface), 0.6)',
            backdropFilter: 'blur(8px)',
          }}>
            <FolderTree onSelectFolder={setCurrentFolderId} />
            <UploadZone folderId={currentFolderId} />
            <PaperList folderId={currentFolderId} />
          </div>
          {/* Right panel */}
          <div style={{ width: '50%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <QuotaBanner />
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <ChatPanel folderIds={currentFolderId ? [currentFolderId] : []} />
              <ChatInput />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
