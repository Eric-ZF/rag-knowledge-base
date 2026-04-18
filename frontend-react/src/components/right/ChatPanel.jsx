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

// Typing dots
function TypingDots() {
  return (
    <div style={{ display: 'flex', gap: '4px', padding: '6px 0' }}>
      {[0, 150, 300].map(delay => (
        <span key={delay} style={{
          width: '6px', height: '6px', borderRadius: '50%',
          background: '#6366f1', opacity: 0.6,
          animation: `bounceDot 1.2s ease-in-out ${delay}ms infinite`,
        }} />
      ))}
    </div>
  )
}

// Markdown renderer
function renderMd(content) {
  if (!content) return null
  return <div dangerouslySetInnerHTML={{ __html: marked.parse(content) }} />
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={handleCopy}
      title="复制答案"
      style={{
        background: 'none', border: 'none', cursor: 'pointer',
        padding: '3px 6px', borderRadius: '6px', fontSize: '10px',
        color: copied ? '#10b981' : 'var(--c-muted)',
        transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: '3px',
        fontFamily: 'inherit',
      }}
      onMouseOver={e => e.currentTarget.style.background = 'var(--c-accent-soft)'}
      onMouseOut={e => e.currentTarget.style.background = 'none'}
    >
      {copied ? '✓ 已复制' : '复制'}
    </button>
  )
}


// Standard academic citations list
function CitationsList({ citations }) {
  if (!citations || citations.length === 0) return null
  return (
    <div style={{
      marginTop: '10px', padding: '12px 14px',
      background: 'rgba(99,102,241,0.04)',
      borderRadius: '12px',
      border: '1px solid rgba(99,102,241,0.12)',
    }}>
      <div style={{
        fontSize: '11px', fontWeight: '700', color: '#6366f1',
        marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '4px',
      }}>
        <BookOpen size={11} />
        参考来源
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {citations.map((cit, i) => (
          <div key={i} style={{ fontSize: '12px', color: 'var(--c-text)', lineHeight: '1.5' }}>
            <span style={{ color: '#6366f1', fontWeight: '600', marginRight: '4px' }}>
              [{i + 1}]
            </span>
            <span style={{ fontWeight: '600' }}>{cit.title || '未知论文'}</span>
            {cit.authors && <span style={{ color: 'var(--c-muted)' }}> — {cit.authors}</span>}
            {cit.year && <span style={{ color: 'var(--c-muted)' }}>, {cit.year}</span>}
            {cit.section_type && cit.section_type !== 'body' && (
              <span style={{ color: 'var(--c-muted)', fontSize: '11px' }}>
                {' '}({cit.section_type === 'abstract' ? '摘要' : cit.section_type === 'introduction' ? '引言' : cit.section_type === 'method' ? '方法' : cit.section_type === 'result' ? '结果' : cit.section_type === 'conclusion' ? '结论' : cit.section_type}, p.{cit.page_number})
              </span>
            )}
            {cit.content && (
              <div style={{
                marginTop: '3px', marginLeft: '16px', fontSize: '11px',
                color: 'var(--c-muted)', borderLeft: '2px solid rgba(99,102,241,0.2)',
                paddingLeft: '8px', fontStyle: 'italic',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                maxWidth: '460px',
              }}>
                「{cit.content.slice(0, 80)}{cit.content.length > 80 ? '…' : ''}」
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Single message bubble
function Bubble({ msg, index }) {
  const isUser = msg.role === 'user'
  const [visibleLen, setVisibleLen] = useState(
    isUser || !msg.content ? msg.content?.length || 0 : 0
  )
  const [typing, setTyping] = useState(false)
  const typingRef = useRef(null)
  const contentRef = useRef(msg.content || '')

  // When full content arrives (streaming done), start typewriter
  useEffect(() => {
    if (isUser || !msg.content) {
      setVisibleLen(msg.content?.length || 0)
      return
    }
    // Start typewriter after content arrives
    contentRef.current = msg.content
    setVisibleLen(0)
    setTyping(true)
    let i = 0
    clearInterval(typingRef.current)
    typingRef.current = setInterval(() => {
      i++
      setVisibleLen(prev => {
        if (prev >= contentRef.current.length) {
          clearInterval(typingRef.current)
          setTyping(false)
          return contentRef.current.length
        }
        return prev + 1
      })
    }, 12) // ~83 chars/sec
    return () => clearInterval(typingRef.current)
  }, [msg.content, isUser])

  const displayText = msg.content?.slice(0, visibleLen) || ''

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      animation: `msgEntrance 0.35s cubic-bezier(0.4,0,0.2,1) ${index * 30}ms both`,
      marginBottom: '14px',
    }}>
      {/* AI Avatar */}
      {!isUser && (
        <div style={{
          width: '34px', height: '34px', borderRadius: '11px', flexShrink: 0,
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginRight: '10px',
          boxShadow: '0 3px 10px rgba(102,126,234,0.35)',
          animation: `avatarPop 0.4s cubic-bezier(0.34,1.56,0.64,1) ${index * 30 + 100}ms both`,
        }}>
          <Bot size={16} color="white" />
        </div>
      )}

      <div style={{ maxWidth: '76%' }}>
        {/* AI label */}
        {!isUser && !msg.thinking && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '4px', marginLeft: '4px' }}>
            <BookOpen size={10} style={{ color: '#6366f1' }} />
            <span style={{ fontSize: '10px', color: '#9ca3af' }}>RAG 检索回答</span>
          </div>
        )}

        {/* Bubble */}
        <div style={{
          padding: isUser ? '10px 16px' : '13px 16px',
          borderRadius: isUser ? '18px 18px 4px 20px' : '18px 18px 18px 4px',
          background: isUser
            ? 'linear-gradient(135deg, #667eea, #764ba2)'
            : 'rgba(255,255,255,0.92)',
          border: isUser ? 'none' : '1px solid var(--c-border)',
          color: isUser ? 'white' : 'var(--c-text)',
          fontSize: '14px', lineHeight: '1.65',
          boxShadow: isUser
            ? '0 4px 16px rgba(102,126,234,0.35)'
            : '0 2px 8px rgba(0,0,0,0.04)',
          wordBreak: 'break-word',
          minWidth: '60px',
        }}>
          {msg.thinking ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--c-muted)', fontSize: '13px' }}>
              <Sparkles size={13} style={{ color: '#6366f1' }} />
              正在检索 & 生成答案
              <TypingDots />
            </div>
          ) : typing ? (
            <span>
              {renderMd(displayText)}
              <span style={{
                display: 'inline-block', width: '2px', height: '14px',
                background: '#6366f1', marginLeft: '1px',
                animation: 'blink 0.8s step-end infinite', verticalAlign: 'text-bottom',
              }} />
            </span>
          ) : (
            renderMd(displayText)
          )}
        </div>

        {/* Citations list */}
        {!isUser && !msg.thinking && msg.citations && msg.citations.length > 0 && !typing && (
          <CitationsList citations={msg.citations} />
        )}

        {/* Copy button for AI answers */}
        {!isUser && !msg.thinking && !typing && msg.content && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
            <CopyBtn text={msg.content} />
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div style={{
          width: '34px', height: '34px', borderRadius: '11px', flexShrink: 0,
          background: 'linear-gradient(135deg, #f093fb, #f5576c)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginLeft: '10px',
          boxShadow: '0 3px 10px rgba(245,87,108,0.3)',
          animation: `avatarPop 0.4s cubic-bezier(0.34,1.56,0.64,1) ${index * 30 + 100}ms both`,
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
    const userMsg = {
      id: Date.now(), role: 'user', content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }
    setMessages(prev => [...prev, userMsg])
    setSending(true)

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const assistantId = Date.now() + 1
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', thinking: true }])

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/chat/stream', {
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
      let fullContent = ''

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
              fullContent += data.content
              // Update content live but don't trigger typing yet
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: fullContent, thinking: false }
                  : m
              ))
            } else if (data.type === 'done') {
              fullContent = data.answer || fullContent
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: fullContent, thinking: false, citations: data.citations || [], meta: data.meta || {} }
                  : m
              ))
            }
          } catch {}
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: '生成答案失败: ' + (e.message || '未知错误'), thinking: false }
            : m
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

  const isEmpty = messages.length === 1 && messages[0].id === 'welcome'

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '20px 24px',
      background: 'transparent',
      display: 'flex', flexDirection: 'column',
    }}>
      {isEmpty && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          paddingBottom: '60px', animation: 'fadeIn 0.5s ease both',
        }}>
          <div style={{
            fontSize: '52px', marginBottom: '16px',
            animation: 'float 3s ease-in-out infinite',
          }}>🔍</div>
          <p style={{ fontSize: '15px', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
            开始你的第一个提问
          </p>
          <p style={{ fontSize: '13px', color: '#9ca3af', textAlign: 'center', maxWidth: '260px' }}>
            上传论文后，可以询问任何关于论文内容的问题
          </p>
          <div style={{
            marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '8px',
            background: 'rgba(99,102,241,0.04)', borderRadius: '14px',
            padding: '14px 18px', border: '1px solid rgba(99,102,241,0.1)',
          }}>
            {['什么是 CBAM？', '这篇论文的研究方法是什么？', '作者的核心结论是什么？'].map((q, i) => (
              <button
                key={i}
                onClick={() => window.__reactSendMessage?.(q)}
                style={{
                  background: 'white', border: '1px solid #e5e7eb',
                  borderRadius: '10px', padding: '7px 14px',
                  fontSize: '12px', color: '#4b5563', cursor: 'pointer',
                  textAlign: 'left', transition: 'all 0.15s',
                  fontFamily: 'inherit',
                }}
                onMouseOver={e => {
                  e.currentTarget.style.borderColor = '#6366f1'
                  e.currentTarget.style.color = '#6366f1'
                  e.currentTarget.style.background = 'rgba(99,102,241,0.04)'
                }}
                onMouseOut={e => {
                  e.currentTarget.style.borderColor = '#e5e7eb'
                  e.currentTarget.style.color = '#4b5563'
                  e.currentTarget.style.background = 'white'
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
      {messages.map((msg, i) => <Bubble key={msg.id} msg={msg} index={i} />)}
      <div ref={bottomRef} />
    </div>
  )
}
