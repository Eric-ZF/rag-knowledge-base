import { useState, useEffect } from 'react'
import { getPapers, deletePaper } from '../../lib/api.js'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useToast } from '../../contexts/ToastContext.jsx'
import { Trash2 } from 'lucide-react'

export default function PaperList() {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [papers, setPapers] = useState([])

  useEffect(() => {
    if (!token) return
    getPapers().then(data => {
      setPapers(data.papers || [])
    }).catch(() => addToast('加载论文失败', 'error'))
  }, [token])

  const handleDelete = async (paperId) => {
    if (!confirm('确认删除这篇论文？')) return
    try {
      await deletePaper(paperId)
      setPapers(prev => prev.filter(p => p.paper_id !== paperId))
      addToast('已删除', 'success')
    } catch (e) {
      addToast(e.message || '删除失败', 'error')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-3.5 py-2">
      <h3 className="text-[11px] font-bold text-[#9ca3af] uppercase tracking-wide mb-2 flex items-center gap-1">
        📄 论文列表
        <span className="ml-auto font-normal normal-case tracking-normal text-[10px] text-[#d1d5db]">
          {papers.length} 篇
        </span>
      </h3>

      {papers.map(p => (
        <div key={p.paper_id}
          className="border border-[#e5e7eb] rounded-lg p-3 mb-1.5 hover:shadow-hover hover:border-accent/20 transition-all bg-white group"
        >
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-[13.5px] font-semibold text-[#111827] leading-snug line-clamp-2">
                {p.title || '无标题'}
              </p>
              {(p.doi || p.journal || p.year) && (
                <p className="text-[11px] text-[#6b7280] mt-1">
                  {p.doi && <span className="text-accent">📄 {p.doi}</span>}
                  {p.journal && <span className="ml-1">📰 {p.journal}{p.year ? ` (${p.year})` : ''}</span>}
                </p>
              )}
              <div className="flex items-center gap-1.5 mt-1.5">
                <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-semibold
                  ${p.status === 'ready' ? 'bg-emerald-50 text-emerald-700' : ''}
                  ${p.status === 'processing' || p.status === 'pending' ? 'bg-amber-50 text-amber-700' : ''}
                  ${p.status === 'error' ? 'bg-red-50 text-red-700' : ''}`}>
                  {p.status === 'ready' ? '✅ 已索引' :
                   p.status === 'processing' ? '⏳ 处理中' :
                   p.status === 'pending' ? '⏳ 排队中' : '❌ 错误'}
                </span>
              </div>
            </div>
            <button
              onClick={() => handleDelete(p.paper_id)}
              className="opacity-0 group-hover:opacity-100 text-[#9ca3af] hover:text-red-500 transition-all bg-transparent border-none cursor-pointer shrink-0 p-1"
              title="删除"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      ))}

      {papers.length === 0 && (
        <p className="text-xs text-[#d1d5db] text-center py-8">暂无论文，上传 PDF 开始</p>
      )}
    </div>
  )
}
