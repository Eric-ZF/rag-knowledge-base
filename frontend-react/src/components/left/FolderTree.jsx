import { useState, useEffect } from 'react'
import { getFolders, createFolder } from '../../lib/api.js'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useToast } from '../../contexts/ToastContext.jsx'
import { FolderOpen, Plus } from 'lucide-react'

export default function FolderTree() {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [folders, setFolders] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')

  useEffect(() => {
    if (!token) return
    getFolders().then(data => {
      setFolders(data.folders || [])
      if (data.folders?.length > 0 && !activeId) {
        setActiveId(data.folders[0].folder_id)
      }
    }).catch(() => addToast('加载文件夹失败', 'error'))
  }, [token])

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const data = await createFolder(newName.trim(), null)
      setFolders(prev => [...prev, data.folder])
      setNewName('')
      setShowNew(false)
      addToast('文件夹已创建', 'success')
    } catch (e) {
      addToast(e.message || '创建失败', 'error')
    }
  }

  return (
    <div className="border-b border-[#e5e7eb]">
      <div className="flex items-center justify-between px-4 py-2.5">
        <span className="text-[11px] font-bold text-[#9ca3af] uppercase tracking-wide flex items-center gap-1">
          <FolderOpen size={12} /> 项目
        </span>
        <button
          onClick={() => setShowNew(v => !v)}
          className="text-[11px] text-accent font-semibold px-1.5 py-0.5 rounded hover:bg-blue-50 transition-colors bg-transparent border-none cursor-pointer"
        >
          <Plus size={12} className="inline" /> 新建
        </button>
      </div>

      {showNew && (
        <div className="px-3 pb-2">
          <input
            type="text"
            placeholder="文件夹名称"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
            className="w-full border border-[#e5e7eb] rounded px-2.5 py-1.5 text-sm
                       focus:outline-none focus:border-accent"
            autoFocus
          />
          <div className="flex gap-2 mt-1.5">
            <button onClick={() => setShowNew(false)} className="flex-1 text-xs text-[#6b7280] border border-[#e5e7eb] rounded py-1 hover:bg-[#f3f4f6] bg-transparent cursor-pointer">取消</button>
            <button onClick={handleCreate} className="flex-1 text-xs text-white bg-accent rounded py-1 hover:bg-accent-hover cursor-pointer border-none">创建</button>
          </div>
        </div>
      )}

      <div>
        {folders.map(f => (
          <div
            key={f.folder_id}
            onClick={() => setActiveId(f.folder_id)}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-sm cursor-pointer transition-colors relative
              ${activeId === f.folder_id
                ? 'bg-blue-50 text-accent font-semibold border-l-2 border-accent'
                : 'text-[#4b5563] hover:bg-[#f3f4f6]'}`}
          >
            <span>📁</span>
            <span className="text-xs">{f.name}</span>
            {f.paper_count != null && (
              <span className="text-[10px] text-[#9ca3af] ml-auto">{f.paper_count}</span>
            )}
          </div>
        ))}
        {folders.length === 0 && (
          <p className="text-xs text-[#9ca3af] px-4 py-2">暂无文件夹</p>
        )}
      </div>
    </div>
  )
}
