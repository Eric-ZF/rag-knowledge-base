import { useState, useEffect, useRef, useCallback } from 'react'
import { getPapers, deletePaper } from '../../lib/api.js'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useToast } from '../../contexts/ToastContext.jsx'
import { useCitation } from '../../contexts/CitationContext.jsx'
import { Trash2, FileText, BookOpen } from 'lucide-react'

function StatusBadge({ status }) {
  const map = {
    ready:     { label: '已索引', bg: 'rgba(16,185,129,0.08)', color: '#10b981', border: 'rgba(16,185,129,0.2)' },
    processing:{ label: '处理中', bg: 'rgba(245,158,11,0.08)', color: '#f59e0b', border: 'rgba(245,158,11,0.2)' },
    pending:   { label: '排队中', bg: 'rgba(99,102,241,0.08)', color: '#6366f1', border: 'rgba(99,102,241,0.2)' },
    error:     { label: '错误',   bg: 'rgba(239,68,68,0.08)',  color: '#ef4444', border: 'rgba(239,68,68,0.2)' },
  }
  const s = map[status] || map.error
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      fontSize: '10px', fontWeight: '600',
      padding: '2px 7px', borderRadius: '999px',
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      {status === 'ready' ? '✓' : status === 'error' ? '✗' : '○'} {s.label}
    </span>
  )
}

// Global tooltip state — single DOM element, rendered once at root
let _tooltipEl = null
function getTooltipEl() {
  if (!_tooltipEl) {
    _tooltipEl = document.createElement('div')
    _tooltipEl.style.cssText = `
      position:fixed;background:#1f2937;color:white;font-size:12px;
      padding:4px 10px;border-radius:6px;white-space:nowrap;
      pointer-events:none;z-index:9999;opacity:0;
      transition:opacity 0.15s;box-shadow:0 2px 8px rgba(0,0,0,0.15);
    `
    document.body.appendChild(_tooltipEl)
  }
  return _tooltipEl
}

function PaperCard({ paper, onDelete }) {
  const { addCitation, removeCitation, citations } = useCitation()
  const isCited = citations.some(c => c.paper_id === paper.paper_id)
  const isReady = paper.status === 'ready'

  const showTooltip = useCallback((e) => {
    if (!isReady) return
    const tip = getTooltipEl()
    tip.textContent = isCited ? '再次点击移除引用' : '点击卡片可直接引用'
    tip.style.opacity = '1'
    positionTooltip(tip, e.currentTarget)
  }, [isReady, isCited])

  const hideTooltip = useCallback(() => {
    const tip = getTooltipEl()
    tip.style.opacity = '0'
  }, [])

  const handleCite = (e) => {
    e.stopPropagation()
    if (isCited) {
      removeCitation(paper.paper_id)
    } else {
      addCitation({ paper_id: paper.paper_id, title: paper.title || '无标题', authors: paper.authors || '', year: paper.year || '' })
    }
  }

  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete(paper.paper_id)
  }

  return (
    <div
      onClick={isReady ? handleCite : undefined}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      style={{
        background: isCited ? 'rgba(99,102,241,0.06)' : 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(12px)',
        border: isCited ? '1.5px solid rgba(99,102,241,0.35)' : '1px solid rgba(0,0,0,0.06)',
        borderRadius: '14px',
        padding: '14px',
        marginBottom: '10px',
        transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        cursor: isReady ? 'pointer' : 'default',
        position: 'relative',
        overflow: 'hidden',
        transform: 'none',
        boxShadow: 'none',
      }}
      onMouseOver={isReady ? (e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 8px 24px rgba(99,102,241,0.12)'
        e.currentTarget.style.borderColor = 'rgba(99,102,241,0.25)'
        const btn = e.currentTarget.querySelector('.delete-btn')
        if (btn) btn.style.opacity = '1'
      } : undefined}
      onMouseOut={isReady ? (e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.borderColor = isCited ? 'rgba(99,102,241,0.35)' : 'rgba(0,0,0,0.06)'
        const btn = e.currentTarget.querySelector('.delete-btn')
        if (btn) btn.style.opacity = '0'
      } : undefined}
    >
      {/* Accent bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '3px',
        background: isCited
          ? 'linear-gradient(90deg, #6366f1, #8b5cf6)'
          : 'linear-gradient(90deg, #667eea, #764ba2)',
        borderRadius: '14px 14px 0 0',
        opacity: isCited ? 1 : 0.7,
      }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        {/* Icon */}
        <div style={{
          width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
          background: 'linear-gradient(135deg, rgba(99,102,241,0.1), rgba(118,75,162,0.1))',
          border: '1px solid rgba(99,102,241,0.12)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <FileText size={16} style={{ color: '#6366f1' }} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            fontSize: '13px', fontWeight: '600', color: '#1a1a2e',
            lineHeight: '1.4', marginBottom: '6px',
            overflow: 'hidden', display: '-webkit-box',
            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {paper.title || '无标题'}
          </p>

          {(paper.authors || paper.journal || paper.year || paper.doi) && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
              {paper.authors && (
                <span style={{ fontSize: '10px', color: '#6b7280', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {paper.authors}
                </span>
              )}
              {paper.journal && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '2px', fontSize: '10px', color: '#6366f1' }}>
                  <BookOpen size={9} /> {paper.journal}{paper.year ? ` · ${paper.year}` : ''}
                </span>
              )}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <StatusBadge status={paper.status} />
          </div>
        </div>

        {/* Delete */}
        <button
          className="delete-btn"
          onClick={handleDelete}
          title="删除论文"
          style={{
            opacity: 0, transition: 'opacity 0.15s',
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '4px', borderRadius: '6px', color: '#9ca3af',
            flexShrink: 0,
          }}
          onMouseOver={e => e.currentTarget.style.color = '#ef4444'}
          onMouseOut={e => e.currentTarget.style.color = '#9ca3af'}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function positionTooltip(tip, cardEl) {
  requestAnimationFrame(() => {
    const rect = cardEl.getBoundingClientRect()
    const tW = tip.offsetWidth || 160
    const tH = tip.offsetHeight || 28
    let left = rect.left + (rect.width - tW) / 2
    let top = rect.top - tH - 10
    if (top < 8) top = rect.bottom + 10
    if (left < 8) left = 8
    if (left + tW > window.innerWidth - 8) left = window.innerWidth - tW - 8
    tip.style.left = left + 'px'
    tip.style.top = top + 'px'
  })
}

export default function PaperList({ folderId }) {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [papers, setPapers] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    getPapers()
      .then(data => {
        const all = Array.isArray(data) ? data : (data.papers || [])
        const filtered = folderId ? all.filter(p => p.folder_id === folderId) : all
        setPapers(filtered)
      })
      .catch(() => addToast('加载论文失败', 'error'))
      .finally(() => setLoading(false))
  }, [token, folderId])

  const handleDelete = async (paperId) => {
    if (!window.confirm('确认删除这篇论文？')) return
    try {
      await deletePaper(paperId)
      setPapers(prev => prev.filter(p => p.paper_id !== paperId))
      addToast('已删除', 'success')
    } catch (e) {
      addToast(e.message || '删除失败', 'error')
    }
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileText size={12} style={{ color: '#6366f1' }} />
          <span style={{ fontSize: '11px', fontWeight: '700', color: '#6b7280', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            论文列表
          </span>
        </div>
        <span style={{ fontSize: '11px', color: '#9ca3af' }}>
          {loading ? '加载中…' : `${papers.length} 篇`}
        </span>
      </div>

      <div>
        {papers.map((p, i) => (
          <div key={p.paper_id} style={{ animation: `fadeSlideUp 0.35s cubic-bezier(0.4,0,0.2,1) ${i * 50}ms both` }}>
            <PaperCard paper={p} onDelete={handleDelete} />
          </div>
        ))}
      </div>

      {papers.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '36px 16px', color: '#9ca3af', animation: 'fadeIn 0.4s ease both' }}>
          <div style={{ fontSize: '40px', marginBottom: '12px', animation: 'float 3s ease-in-out infinite' }}>📄</div>
          <p style={{ fontSize: '13px', fontWeight: '500', color: '#6b7280', marginBottom: '4px' }}>暂无论文</p>
          <p style={{ fontSize: '12px', color: '#d1d5db' }}>上传 PDF 开始使用</p>
        </div>
      )}

      {loading && papers.length === 0 && (
        <div>
          {[1,2,3].map(i => (
            <div key={i} style={{
              height: '88px', borderRadius: '14px', marginBottom: '10px',
              background: 'linear-gradient(90deg, #f0f2f8 25%, #e8ecf3 50%, #f0f2f8 75%)',
              backgroundSize: '200% 100%',
              animation: `shimmer 1.5s infinite ${i * 100}ms`,
            }} />
          ))}
        </div>
      )}
    </div>
  )
}
