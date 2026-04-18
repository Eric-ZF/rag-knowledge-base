import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'
import FolderTree from './left/FolderTree.jsx'
import UploadZone from './left/UploadZone.jsx'
import PaperList from './left/PaperList.jsx'
import QuotaBanner from './right/QuotaBanner.jsx'
import ChatPanel from './right/ChatPanel.jsx'
import ChatInput from './right/ChatInput.jsx'

export default function MainLayout() {
  const { userPhone, logout } = useAuth()
  const [currentFolderId, setCurrentFolderId] = useState(null)

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
        padding: '0 20px', gap: '12px', shrink: 0,
        background: 'rgba(255,255,255,0.8)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
        borderBottom: '1px solid var(--c-border)',
        position: 'relative', zIndex: 10,
      }}>
        {/* Logo */}
        <div style={{
          width: '32px', height: '32px', borderRadius: '10px',
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '16px', boxShadow: '0 2px 8px rgba(102,126,234,0.3)',
        }}>
          📚
        </div>
        <h1 style={{ fontSize: '15px', fontWeight: '700', color: '#1a1a2e' }}>
          RAG 学术知识库
        </h1>
        <span className="badge badge-accent" style={{ fontSize: '11px' }}>
          Phase 0
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '13px', color: '#6b7280' }}>{userPhone}</span>
          <button
            onClick={logout}
            style={{
              fontSize: '12px', color: '#9ca3af', cursor: 'pointer',
              background: 'none', border: 'none', padding: '4px 8px',
              borderRadius: '8px', transition: 'all 0.15s',
            }}
            onMouseOver={e => e.target.style.color = '#ef4444'}
            onMouseOut={e => e.target.style.color = '#9ca3af'}
          >
            退出
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left panel */}
        <div style={{
          width: '50%', display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          borderRight: '1px solid var(--c-border)',
          background: 'rgba(255,255,255,0.6)',
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
    </div>
  )
}
