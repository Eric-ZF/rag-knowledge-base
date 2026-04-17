import { useState, useEffect, useRef, useCallback } from 'react'
import { marked } from 'marked'
import { BookOpen } from 'lucide-react'

marked.setOptions({ mangle: false, headerIds: false })

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content: `👋 欢迎！上传你的第一篇论文，然后在这里问我任何问题。\n\n例如：「这篇论文的核心结论是什么？」「作者用了什么方法？」`,
}

export default function ChatPanel({ folderIds = [] }) {
  const [messages, setMessages] = useState([WELCOME])
  const [sending, setSending] = useState(false)
  const [currentText, setCurrentText] = useState('')
  const bottomRef = useRef()
  const abortRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentText])

  const sendMessage = useCallback(async (text, mode = 'default') => {
    if (!text.trim() || sending) return
    const userMsg = { id: Date.now(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setSending(true)
    setCurrentText('')

    // Cancel any existing stream
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const assistantId = Date.now() + 1
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', thinking: true }])

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('http://124.156.204.163:8080/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: text,
          mode,
          folder_ids: folderIds,
          collection_name: null,
          paper_ids: null,
        }),
        signal: controller.signal,
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + data.content, thinking: false } : m
              ))
            } else if (data.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: data.answer || m.content, thinking: false } : m
              ))
            }
          } catch {}
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: '生成答案失败: ' + (e.message || '未知错误'), thinking: false } : m
        ))
      }
    } finally {
      setSending(false)
    }
  }, [sending, folderIds])

  // Expose sendMessage globally for ChatInput
  useEffect(() => {
    window.__reactSendMessage = sendMessage
    return () => { window.__reactSendMessage = null }
  }, [sendMessage])

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
            {msg.role === 'assistant' && !msg.content && !msg.thinking && (
              <div className="mb-1.5"><BookOpen size={12} className="text-accent inline" /></div>
            )}
            {msg.thinking ? (
              <div className="flex gap-1 mt-1">
                <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
                <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
                <span className="w-1.5 h-1.5 bg-[#9ca3af] rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
              </div>
            ) : renderContent(msg.content)}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
