import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function AuthScreen() {
  const { login, register, loading, error } = useAuth()
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
    <div className="min-h-screen bg-[#f9fafb] flex items-center justify-center p-4">
      <div className="bg-white border border-[#e5e7eb] rounded-lg shadow-lg w-full max-w-[380px] p-8">
        {/* Logo / Title */}
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-[#111827] mb-1">RAG 学术知识库</h1>
          <p className="text-sm text-[#6b7280]">基于私有论文库的智能问答</p>
        </div>

        {/* Error */}
        {(localError || error) && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-4">
            {localError || error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="tel"
            placeholder="手机号"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            className="w-full border border-[#e5e7eb] rounded-md px-3 py-2.5 text-sm
                       focus:outline-none focus:border-accent transition-colors"
            autoComplete="tel"
          />
          <input
            type="password"
            placeholder="密码"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border border-[#e5e7eb] rounded-md px-3 py-2.5 text-sm
                       focus:outline-none focus:border-accent transition-colors"
            autoComplete="current-password"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent text-white rounded-md py-2.5 text-sm font-semibold
                       hover:bg-accent-hover transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? '处理中…' : '登录'}
          </button>
        </form>

        {/* Toggle */}
        <p className="text-center text-sm text-[#6b7280] mt-4">
          {isLogin ? '还没有账号？' : '已有账号？'}
          <button
            type="button"
            onClick={() => { setIsLogin(v => !v); setLocalError('') }}
            className="text-accent font-semibold ml-1 hover:underline bg-transparent border-none cursor-pointer"
          >
            {isLogin ? '注册' : '登录'}
          </button>
        </p>
      </div>
    </div>
  )
}
