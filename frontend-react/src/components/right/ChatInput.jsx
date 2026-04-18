import { useState, useRef, useEffect } from 'react'
import { SendHorizonal, MessageSquare, FlaskConical, FileSearch } from 'lucide-react'

const MODES = [
  { key: 'default',    label: '默认问答',     icon: MessageSquare },
  { key: 'methodology', label: '方法论审计', icon: FlaskConical },
  { key: 'survey',     label: '文献综述',    icon: FileSearch },
]

export default function ChatInput() {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('default')
  const textareaRef = useRef()

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSend = () => {
    if (!text.trim()) return
    window.__reactSendMessage?.(text, mode)
    setText('')
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
                border: active ? '1.5px solid #6366f1' : '1.5px solid #e5e7eb',
                background: active ? 'rgba(99,102,241,0.08)' : 'white',
                color: active ? '#6366f1' : '#6b7280',
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
        background: 'white', borderRadius: '16px',
        border: '1.5px solid #e5e7eb',
        padding: '10px 14px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
        onFocus={() => {}}
        onBlur={() => {}}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder="问我关于你论文库的任何问题…"
          style={{
            flex: 1, resize: 'none', border: 'none', outline: 'none',
            fontSize: '14px', lineHeight: '1.6', color: '#374151',
            background: 'transparent', maxHeight: '120px',
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim()}
          style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: text.trim()
              ? 'linear-gradient(135deg, #667eea, #764ba2)'
              : '#f3f4f6',
            border: 'none', cursor: text.trim() ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
            boxShadow: text.trim() ? '0 4px 12px rgba(102,126,234,0.35)' : 'none',
            flexShrink: 0,
          }}
        >
          <SendHorizonal size={15} color={text.trim() ? 'white' : '#9ca3af'} />
        </button>
      </div>
    </div>
  )
}
