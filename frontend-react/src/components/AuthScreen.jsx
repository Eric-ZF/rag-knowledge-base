import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function AuthScreen() {
  const { login, loading, error } = useAuth()
  const [isLogin, setIsLogin] = useState(true)
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalError('')
    if (!phone.trim()) return setLocalError('请输入手机号')
    if (password.length < 6) return setLocalError('密码至少 6 位')
    try {
      await login(phone, password)
    } catch (e) {
      setLocalError(e.message || '登录失败')
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 60%, #f093fb 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Floating orbs */}
      <div style={{
        position: 'absolute', width: '400px', height: '400px',
        borderRadius: '50%', background: 'rgba(255,255,255,0.08)',
        top: '-100px', right: '-80px', filter: 'blur(40px)',
        animation: 'float 6s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', width: '300px', height: '300px',
        borderRadius: '50%', background: 'rgba(255,255,255,0.06)',
        bottom: '-60px', left: '-60px', filter: 'blur(30px)',
        animation: 'float 5s ease-in-out infinite 1s',
      }} />

      {/* Card */}
      <div className="glass-card animate-fade-up" style={{
        width: '100%', maxWidth: '420px',
        borderRadius: '24px', padding: '40px',
        position: 'relative', zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '16px',
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 24px rgba(102,126,234,0.4)',
            fontSize: '24px',
          }}>
            📚
          </div>
          <h1 style={{
            fontSize: '22px', fontWeight: '700',
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: '6px',
          }}>
            RAG 学术知识库
          </h1>
          <p style={{ fontSize: '13px', color: '#6b7280' }}>
            基于私有论文库的智能问答助手
          </p>
        </div>

        {/* Error */}
        {(localError || error) && (
          <div style={{
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: '12px', padding: '10px 14px', marginBottom: '20px',
            fontSize: '13px', color: '#ef4444', textAlign: 'center',
            animation: 'fadeIn 0.2s ease',
          }}>
            {localError || error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <input
            type="tel"
            placeholder="手机号"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            className="input-field"
            autoComplete="tel"
          />
          <input
            type="password"
            placeholder="密码（至少 6 位）"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="input-field"
            autoComplete="current-password"
          />
          <button
            type="submit"
            disabled={loading}
            className="btn-primary"
            style={{ width: '100%', padding: '13px', fontSize: '15px', marginTop: '4px' }}
          >
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                <span className="animate-spin" style={{ display: 'inline-block', width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
                处理中…
              </span>
            ) : '登录'}
          </button>
        </form>

        {/* Toggle hint */}
        <p style={{ textAlign: 'center', fontSize: '13px', color: '#6b7280', marginTop: '24px' }}>
          {isLogin ? '还没有账号？' : '已有账号？'}
          <button
            type="button"
            onClick={() => { setIsLogin(v => !v); setLocalError('') }}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#6366f1', fontWeight: '600', marginLeft: '6px',
              fontSize: '13px',
            }}
          >
            {isLogin ? '注册' : '登录'}
          </button>
        </p>

        {/* Demo hint */}
        <div style={{
          marginTop: '20px', padding: '12px',
          background: 'rgba(99,102,241,0.05)', borderRadius: '12px',
          border: '1px solid rgba(99,102,241,0.1)',
          fontSize: '12px', color: '#6b7280', textAlign: 'center',
        }}>
          测试账号：13800138000 / BossPhase0
        </div>
      </div>
    </div>
  )
}
