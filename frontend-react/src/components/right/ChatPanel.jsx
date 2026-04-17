import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { useToast } from '../../contexts/ToastContext.jsx'
import { sendChat } from '../../lib/api.js'
import { marked } from 'marked'
import { BookOpen } from 'lucide-react'

marked.setOptions({ mangle: false, headerIds: false })

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content: `👋 欢迎！上传你的第一篇论文，然后在这里问我任何问题。\n\n例如：「这篇论文的核心结论是什么？」「作者用了什么方法？」`,
}

export default function ChatPanel() {
  const { token } = useAuth()
  const { addToast } = useToast()
  const [messages, setMessages] = useState([WELCOME])
  const [sending, setSending] = useState(false)
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Expose sendMessage globally for ChatInput
  useEffect(() => {
    window.__reactSendMessage = async (text) => {
      if (!text.trim() || sending) return
      const userMsg = { id: Date.now(), role: 'user', content: text }
      setMessages(prev => [...prev, userMsg])
      setSending(true)

      try {
        const data = await sendChat({
          message: text,
          mode: 'default',
          collection_name: null,
        })
        // SSE response
        if (data.event === 'success' || data.answer) {
          const aiMsg = { id: Date.now() + 1, role: 'assistant', content: data.answer || '' }
          setMessages(prev => [...prev, aiMsg])
        } else {
          addToast('生成答案失败', 'error')
        }
      } catch (e) {
        addToast(e.message || '生成答案失败', 'error')
      } finally {
        setSending(false)
      }
    }
    return () => { window.__reactSendMessage = null }
  }, [sending, addToast])

  const renderContent = (content) => {
    if (!content) return null
    const html = marked.parse(content)
    return <div dangerouslySetInnerHTML={{ __html: html }} />
  }

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
      {messages.map(msg => (
        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[82%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed
            ${msg.role === 'user'
              ? 'bg-accent text-white'
              : 'bg-white border border-[#e5e7eb] text-[#374151]'}`}
          >
            {msg.role === 'assistant' && (
              <div className="mb-1.5">
                <BookOpen size={12} className="text-accent inline" />
              </div>
            )}
            {renderContent(msg.content)}
          </div>
        </div>
      ))}
      {sending && (
        <div className="flex justify-start">
          <div className="bg-white border border-[#e5e7eb] rounded-lg px-3.5 py-2.5">
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
              <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
              <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
