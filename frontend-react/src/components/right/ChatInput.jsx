import { useState, useRef, useEffect } from 'react'
import { SendHorizonal, MessageSquare, FlaskConical, FileSearch } from 'lucide-react'
import { useCitation } from '../../contexts/CitationContext.jsx'

const MODES = [
  { key: 'default',    label: '默认问答',     icon: MessageSquare },
  { key: 'methodology', label: '方法论审计', icon: FlaskConical },
  { key: 'survey',     label: '文献综述',    icon: FileSearch },
]

export default function ChatInput() {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('default')
  const textareaRef = useRef()
  const { citations, removeCitation, clearCitations, getCitationPrefix } = useCitation()

  const autoResize = (el) => {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSend = () => {
    if (!text.trim() && citations.length === 0) return
    const citeBlock = citations.length > 0 ? getCitationPrefix() + '\n\n' : ''
    const fullText = citeBlock + text.trim()
    window.__reactSendMessage?.(fullText, mode)
    setText('')
    clearCitations()
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{
      padding: '12px 24px 16px',
      background: 'rgba(255,255,255,0.85)',
      backdropFilter: 'blur(16px)',
      borderTop: '1px solid var(--c-border)',
    }}>
      {/* Citation bar */}
      {citations.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
          {citations.map((c, i) => (
            <div key={c.paper_id} style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px',
              background: 'white', border: '1.5px solid rgba(99,102,241,0.3)',
              borderRadius: '20px', padding: '3px 8px 3px 10px',
              fontSize: '12.5px', color: '#4b5563', maxWidth: '340px',
              boxShadow: '0 1px 3px rgba(99,102,241,0.08)',
            }}>
              <span style={{ color: '#6366f1', fontWeight: '700', flexShrink: 0 }}>[{i + 1}]</span>
              <span style={{
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                maxWidth: '220px',
              }} title={c.title + (c.authors ? ` (${c.authors}${c.year ? ', ' + c.year : ''})` : '')}>
                {c.title}{c.authors ? ` (${c.authors}${c.year ? ', ' + c.year : ''})` : ''}
              </span>
              <button
                onClick={() => removeCitation(c.paper_id)}
                title="移除引用"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#9ca3af', fontSize: '14px', lineHeight: 1,
                  padding: '0 0 0 2px', borderRadius: '50%',
                  transition: 'color 0.15s, background 0.15s', flexShrink: 0,
                }}
                onMouseOver={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = '#fee2e2' }}
                onMouseOut={e => { e.currentTarget.style.color = '#9ca3af'; e.currentTarget.style.background = 'none' }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Mode buttons */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
        {MODES.map(m => {
          const Icon = m.icon
          const active = mode === m.key
          return (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                padding: '5px 12px', borderRadius: '999px', fontSize: '12px',
                fontWeight: active ? '600' : '500',
                cursor: 'pointer', transition: 'all 0.15s',
                border: active ? '1.5px solid #6366f1' : '1.5px solid var(--c-border)',
                background: active ? 'rgba(99,102,241,0.08)' : 'var(--c-surface)',
                color: active ? '#6366f1' : 'var(--c-muted)',
                boxShadow: active ? '0 0 0 3px rgba(99,102,241,0.08)' : 'none',
              }}
            >
              <Icon size={12} />
              {m.label}
            </button>
          )
        })}
      </div>

      {/* Input row */}
      <div style={{
        display: 'flex', alignItems: 'flex-end', gap: '10px',
        background: 'var(--c-surface)', borderRadius: '16px',
        border: '1.5px solid var(--c-border)',
        padding: '10px 14px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
        onFocus={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.5)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.08)' }}
        onBlur={e => { e.currentTarget.style.borderColor = 'var(--c-border)'; e.currentTarget.style.boxShadow = 'none' }}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={e => { setText(e.target.value); autoResize(e.target) }}
          onKeyDown={handleKey}
          placeholder="问我关于你论文库的任何问题…"
          style={{
            flex: 1, resize: 'none', border: 'none', outline: 'none',
            fontSize: '14px', lineHeight: '1.6', color: 'var(--c-text)',
            background: 'transparent', maxHeight: '120px',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim() && citations.length === 0}
          style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: (text.trim() || citations.length > 0)
              ? 'linear-gradient(135deg, #667eea, #764ba2)'
              : '#f3f4f6',
            border: 'none', cursor: (text.trim() || citations.length > 0) ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
            boxShadow: (text.trim() || citations.length > 0) ? '0 4px 12px rgba(102,126,234,0.35)' : 'none',
            flexShrink: 0,
          }}
        >
          <SendHorizonal size={15} color={text.trim() || citations.length > 0 ? 'white' : '#9ca3af'} />
        </button>
      </div>
    </div>
  )
}
