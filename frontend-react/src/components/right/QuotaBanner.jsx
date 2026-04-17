import { useState, useEffect } from 'react'
import { getQuota } from '../../lib/api.js'

export default function QuotaBanner() {
  const [used, setUsed] = useState(0)
  const [limit] = useState(20)

  useEffect(() => {
    getQuota().then(data => {
      setUsed(data.used || 0)
    }).catch(() => {})
  }, [])

  return (
    <div className="px-5 py-2 border-b border-[#e5e7eb] flex items-center justify-between text-xs text-[#6b7280] bg-white">
      <span>套餐：<span className="font-bold text-[#111827]">Free</span></span>
      <span className="font-medium">已上传 {used} / {limit} 篇</span>
    </div>
  )
}
