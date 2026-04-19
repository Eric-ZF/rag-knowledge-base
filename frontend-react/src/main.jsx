import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

const BUILD_VERSION = '20260419' // 每次 npm run build 时自动更新

// 服务端下发当前部署版本，前端对比，不一致则强制刷新
fetch('/api/version', { headers: { 'Cache-Control': 'no-cache' } })
  .then(r => r.ok ? r.text() : null)
  .then(ver => {
    if (ver && ver.trim() !== BUILD_VERSION.trim()) {
      // 版本不一致，强制刷新获取最新资源
      window.location.reload()
      return
    }
    renderApp()
  })
  .catch(() => renderApp()) // 网络问题则继续

function renderApp() {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}
