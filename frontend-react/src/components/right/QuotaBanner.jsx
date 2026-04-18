import { useState, useEffect } from 'react'
import { getQuota } from '../../lib/api.js'

export default function QuotaBanner() {
  const [quota, setQuota] = useState({ papers_used: 0, papers_limit: 999, plan: 'pro' })

  useEffect(() => {
    getQuota().then(data => setQuota(data)).catch(() => {})
  }, [])

  const pct = Math.min((quota.papers_used / quota.papers_limit) * 100, 100)
  const isPro = quota.plan === 'pro'

  return (
    <div style={{
      padding: '8px 20px',
      borderBottom: '1px solid var(--c-border)',
      background: 'rgba(255,255,255,0.6)',
      backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      fontSize: '12px',
    }}>
      {/* Plan badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{
          fontSize: '10px', fontWeight: '700', padding: '2px 8px', borderRadius: '999px',
          background: isPro ? 'linear-gradient(135deg, rgba(102,126,234,0.12), rgba(118,75,162,0.12))' : 'rgba(107,114,128,0.08)',
          color: isPro ? '#6366f1' : '#6b7280',
          border: `1px solid ${isPro ? 'rgba(99,102,241,0.2)' : 'rgba(0,0,0,0.08)'}`,
          letterSpacing: '0.04em',
        }}>
          {isPro ? '⭐ Pro' : 'Free'}
        </span>
        <span style={{ color: '#6b7280' }}>
          已上传 <strong style={{ color: '#1a1a2e', fontWeight: '600' }}>{quota.papers_used}</strong>
          <span style={{ color: '#d1d5db', margin: '0 2px' }}>/</span>
          {quota.papers_limit} 篇
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          width: '80px', height: '4px', borderRadius: '99px',
          background: 'rgba(0,0,0,0.06)', overflow: 'hidden',
        }}>
          <div style={{
            width: `${pct}%`, height: '100%',
            background: pct > 80
              ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
              : 'linear-gradient(90deg, #667eea, #764ba2)',
            borderRadius: '99px',
            transition: 'width 0.5s ease',
          }} />
        </div>
        {pct > 80 && (
          <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: '600' }}>容量紧张</span>
        )}
      </div>
    </div>
  )
}
