import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login, register, setPassword, getToken, setToken } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(getToken())
  const [userPhone, setUserPhone] = useState(localStorage.getItem('phone') || '')
  const [userId, setUserId] = useState(localStorage.getItem('userId') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const doLogin = useCallback(async (phone, password) => {
    setLoading(true)
    setError('')
    try {
      const data = await login(phone.trim(), password)
      setTokenState(data.access_token)
      setToken(data.access_token)
      localStorage.setItem('phone', phone.trim())
      localStorage.setItem('userId', data.user_id || phone)
      setUserPhone(phone.trim())
      setUserId(data.user_id || phone)
      return data
    } catch (e) {
      setError(e.message || '登录失败')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const doRegister = useCallback(async (phone, password) => {
    setLoading(true)
    setError('')
    try {
      const data = await register(phone.trim(), password)
      return data
    } catch (e) {
      setError(e.message || '注册失败')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const doSetPassword = useCallback(async (phone, password) => {
    setLoading(true)
    setError('')
    try {
      const data = await setPassword(phone.trim(), password)
      return data
    } catch (e) {
      setError(e.message || '设置密码失败')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    setTokenState('')
    setToken('')
    setUserPhone('')
    setUserId('')
    localStorage.removeItem('token')
    localStorage.removeItem('phone')
    localStorage.removeItem('userId')
  }, [])

  return (
    <AuthContext.Provider value={{
      token, userPhone, userId,
      loading, error,
      login: doLogin, register: doRegister, setPassword: doSetPassword, logout,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
