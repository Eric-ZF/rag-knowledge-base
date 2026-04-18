import { useState, useEffect } from 'react'
import { getFolders, createFolder } from '../../lib/api.js'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useToast } from '../../contexts/ToastContext.jsx'
import { FolderOpen, Plus, Folder } from 'lucide-react'

export default function FolderTree({ onSelectFolder }) {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [folders, setFolders] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')

  useEffect(() => {
    if (!token) return
    getFolders().then(data => {
      const arr = Array.isArray(data) ? data : (data.folders || [])
      setFolders(arr)
      if (arr.length > 0 && !activeId) {
        setActiveId(arr[0].folder_id)
        onSelectFolder?.(arr[0].folder_id)
      }
    }).catch(() => addToast('加载文件夹失败', 'error'))
  }, [token])

  const handleSelect = (id) => {
    setActiveId(id)
    onSelectFolder?.(id)
    localStorage.setItem('currentFolderId', id)
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const data = await createFolder(newName.trim(), null)
      const newFolder = Array.isArray(data) ? data : data.folder || data
      setFolders(prev => [...prev, newFolder])
      setNewName('')
      setShowNew(false)
      addToast('文件夹已创建', 'success')
    } catch (e) {
      addToast(e.message || '创建失败', 'error')
    }
  }

  return (
    <div style={{
      borderBottom: '1px solid var(--c-border)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FolderOpen size={13} style={{ color: '#6366f1' }} />
          <span style={{
            fontSize: '11px', fontWeight: '700', color: '#6b7280',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            项目
          </span>
        </div>
        <button
          onClick={() => setShowNew(v => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            fontSize: '11px', fontWeight: '600', color: '#6366f1',
            background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
            borderRadius: '8px', padding: '3px 8px', cursor: 'pointer',
            transition: 'all 0.15s',
          }}
          onMouseOver={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.12)' }}
          onMouseOut={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.06)' }}
        >
          <Plus size={11} /> 新建
        </button>
      </div>

      {showNew && (
        <div style={{ padding: '0 12px 12px' }}>
          <input
            type="text"
            placeholder="文件夹名称"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            className="input-field"
            autoFocus
            style={{ marginBottom: '8px', fontSize: '13px' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => setShowNew(false)} className="btn-ghost" style={{ flex: 1, fontSize: '12px', padding: '6px' }}>
              取消
            </button>
            <button onClick={handleCreate} className="btn-primary" style={{ flex: 1, fontSize: '12px', padding: '6px' }}>
              创建
            </button>
          </div>
        </div>
      )}

      <div style={{ paddingBottom: '4px' }}>
        {folders.map((f, i) => (
          <div
            key={f.folder_id}
            onClick={() => handleSelect(f.folder_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '9px 16px', cursor: 'pointer',
              transition: 'all 0.15s',
              borderLeft: activeId === f.folder_id ? '3px solid #6366f1' : '3px solid transparent',
              background: activeId === f.folder_id
                ? 'rgba(99,102,241,0.06)'
                : 'transparent',
              color: activeId === f.folder_id ? '#6366f1' : '#4b5563',
              fontWeight: activeId === f.folder_id ? '600' : '400',
              animation: `fadeSlideUp 0.3s cubic-bezier(0.4,0,0.2,1) ${i * 40}ms both`,
            }}
            onMouseOver={e => { if (activeId !== f.folder_id) e.currentTarget.style.background = 'rgba(0,0,0,0.02)' }}
            onMouseOut={e => { if (activeId !== f.folder_id) e.currentTarget.style.background = 'transparent' }}
          >
            <Folder size={14} style={{ color: activeId === f.folder_id ? '#6366f1' : '#9ca3af', flexShrink: 0 }} />
            <span style={{ fontSize: '13px', flex: 1 }}>{f.name}</span>
            {f.paper_count != null && f.paper_count > 0 && (
              <span style={{
                fontSize: '10px', fontWeight: '600',
                background: activeId === f.folder_id ? 'rgba(99,102,241,0.15)' : '#f3f4f6',
                color: activeId === f.folder_id ? '#6366f1' : '#9ca3af',
                padding: '1px 6px', borderRadius: '999px',
              }}>
                {f.paper_count}
              </span>
            )}
          </div>
        ))}
        {folders.length === 0 && (
          <p style={{ fontSize: '12px', color: '#9ca3af', padding: '16px', textAlign: 'center' }}>
            暂无文件夹
          </p>
        )}
      </div>
    </div>
  )
}
