import { useState, useEffect, useRef, useCallback } from 'react'
import { marked } from 'marked'
import { Bot, User, BookOpen, Sparkles } from 'lucide-react'

marked.setOptions({ mangle: false, headerIds: false })

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content: `👋 欢迎使用 RAG 学术知识库！

上传论文后，我可以从论文内容中回答你的问题。例如：
• 「这篇论文的核心结论是什么？」
• 「作者采用了什么研究方法？」
• 「与碳边境调节机制相关的论文有哪些？」`,
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: '4px', padding: '4px 0' }}>
      {[0, 150, 300].map(delay => (
        <span key={delay} style={{
          width: '7px', height: '7px', borderRadius: '50%',
          background: '#6366f1', opacity: 0.5,
          animation: `bounce 1.2s ease-in-out ${delay}ms infinite`,
        }} />
      ))}
    </div>
  )
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'

  const renderContent = (content) => {
    if (!content) return null
    const html = marked.parse(content)
    return <div dangerouslySetInnerHTML={{ __html: html }} />
  }

  return (
    <div style={{
      display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start',
      animation: 'fadeSlideUp 0.3s cubic-bezier(0.4,0,0.2,1) both',
      marginBottom: '12px',
    }}>
      {!isUser && (
        <div style={{
          width: '32px', height: '32px', borderRadius: '10px', flexShrink: 0,
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginRight: '10px', boxShadow: '0 2px 8px rgba(102,126,234,0.3)',
        }}>
          <Bot size={16} color="white" />
        </div>
      )}

      <div style={{ maxWidth: '75%' }}>
        {isUser && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            justifyContent: 'flex-end', marginBottom: '4px',
          }}>
            <span style={{ fontSize: '11px', color: '#6b7280' }}>{msg.time || ''}</span>
          </div>
        )}

        <div style={{
          padding: isUser ? '10px 16px' : '12px 16px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          background: isUser
            ? 'linear-gradient(135deg, #667eea, #764ba2)'
            : 'rgba(255,255,255,0.9)',
          border: isUser ? 'none' : '1px solid rgba(0,0,0,0.06)',
          color: isUser ? 'white' : '#374151',
          fontSize: '14px', lineHeight: '1.6',
          boxShadow: isUser ? '0 4px 16px rgba(102,126,234,0.35)' : '0 2px 8px rgba(0,0,0,0.04)',
          wordBreak: 'break-word',
        }}>
          {msg.thinking ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280', fontSize: '13px', padding: '2px 0' }}>
              <Sparkles size={14} style={{ color: '#6366f1' }} />
              思考中…
              <TypingIndicator />
            </div>
          ) : (
            renderContent(msg.content)
          )}
        </div>

        {!isUser && !msg.thinking && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', paddingLeft: '4px' }}>
            <BookOpen size={10} style={{ color: '#6366f1' }} />
            <span style={{ fontSize: '10px', color: '#9ca3af' }}>RAG 检索回答</span>
          </div>
        )}
      </div>

      {isUser && (
        <div style={{
          width: '32px', height: '32px', borderRadius: '10px', flexShrink: 0,
          background: 'linear-gradient(135deg, #f093fb, #f5576c)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginLeft: '10px', boxShadow: '0 2px 8px rgba(245,87,108,0.3)',
        }}>
          <User size={16} color="white" />
        </div>
      )}
    </div>
  )
}

export default function ChatPanel({ folderIds = [] }) {
  const [messages, setMessages] = useState([WELCOME])
  const [sending, setSending] = useState(false)
  const bottomRef = useRef()
  const abortRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async (text, mode = 'default') => {
    if (!text.trim() || sending) return
    const userMsg = { id: Date.now(), role: 'user', content: text, time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
    setMessages(prev => [...prev, userMsg])
    setSending(true)

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
        body: JSON.stringify({ question: text, mode, folder_ids: folderIds }),
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

  useEffect(() => {
    window.__reactSendMessage = sendMessage
    return () => { window.__reactSendMessage = null }
  }, [sendMessage])

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '20px 24px',
      background: 'transparent',
    }}>
      {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
      <div ref={bottomRef} />
    </div>
  )
}
