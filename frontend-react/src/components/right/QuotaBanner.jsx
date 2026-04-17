import { useState, useEffect } from 'react'
import { getQuota } from '../../lib/api.js'

export default function QuotaBanner() {
  const [quota, setQuota] = useState({ papers_used: 0, papers_limit: 999, plan: 'pro' })

  useEffect(() => {
    getQuota().then(data => {
      setQuota(data)
    }).catch(() => {})
  }, [])

  return (
    <div className="px-5 py-2 border-b border-[#e5e7eb] flex items-center justify-between text-xs text-[#6b7280] bg-white">
      <span>套餐：<span className="font-bold text-[#111827]">{quota.plan === 'pro' ? 'Pro' : 'Free'}</span></span>
      <span className="font-medium">已上传 {quota.papers_used} / {quota.papers_limit} 篇</span>
    </div>
  )
}
