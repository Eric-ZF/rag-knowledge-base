import { useState, useRef, useEffect } from 'react'
import { SendHorizonal } from 'lucide-react'

export default function ChatInput() {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('default')
  const textareaRef = useRef()

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSend = () => {
    if (!text.trim()) return
    window.__reactSendMessage?.(text)
    setText('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const modes = [
    { key: 'default', label: '💬 默认问答' },
    { key: 'methodology', label: '🔬 方法论审计' },
    { key: 'survey', label: '📝 文献综述' },
  ]

  return (
    <div className="px-5 py-3 border-t border-[#e5e7eb] bg-white">
      {/* Mode buttons */}
      <div className="flex gap-1.5 mb-2 flex-wrap">
        {modes.map(m => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`text-xs px-3 py-1 rounded-full border font-medium transition-colors cursor-pointer
              ${mode === m.key
                ? 'bg-accent text-white border-accent'
                : 'bg-white text-[#4b5563] border-[#e5e7eb] hover:border-accent/30 hover:text-accent'}`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div className="flex items-end gap-2 border border-[#e5e7eb] rounded-lg px-3.5 py-2 focus-within:border-accent transition-colors">
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder="问我关于你论文库的任何问题…"
          className="flex-1 resize-none text-sm leading-relaxed text-[#374151] placeholder:text-[#9ca3af]
                     focus:outline-none bg-transparent"
          style={{ maxHeight: '120px' }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim()}
          className="shrink-0 w-9 h-9 bg-accent text-white rounded-md flex items-center justify-center
                     hover:bg-accent-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer border-none"
        >
          <SendHorizonal size={16} />
        </button>
      </div>
    </div>
  )
}
