import { useRef, useState } from 'react'
import { uploadPaper } from '../../lib/api.js'
import { useToast } from '../../contexts/ToastContext.jsx'
import { Upload, FileUp } from 'lucide-react'

export default function UploadZone({ folderId }) {
  const { addToast } = useToast()
  const inputRef = useRef()
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = async (files) => {
    const pdfs = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length === 0) return addToast('仅支持 PDF 文件', 'warning')
    setUploading(true)

    try {
      const formData = new FormData()
      pdfs.forEach(f => formData.append('files', f))
      if (folderId) formData.append('folder_id', folderId)

      const result = await uploadPaper(formData)
      if (result.success || result.total !== undefined) {
        addToast(`${pdfs.length} 篇论文已提交索引`, 'success')
        setTimeout(() => window.location.reload(), 1500)
      } else {
        addToast(result.detail || '上传失败', 'error')
      }
    } catch (e) {
      addToast(e.message || '上传失败', 'error')
    } finally {
      setUploading(false)
    }
  }

  const borderColor = dragOver ? '#6366f1' : '#e5e7eb'
  const bgColor = dragOver ? 'rgba(99,102,241,0.04)' : 'rgba(249,250,251,0.8)'

  return (
    <div
      style={{
        margin: '8px 14px',
        border: `2px dashed ${borderColor}`,
        borderRadius: '14px',
        padding: '16px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        background: bgColor,
        backdropFilter: 'blur(8px)',
      }}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
      onMouseOver={e => { if (!dragOver) e.currentTarget.style.borderColor = '#6366f1' }}
      onMouseOut={e => { if (!dragOver) e.currentTarget.style.borderColor = '#e5e7eb' }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={e => handleFiles(e.target.files)}
      />

      {uploading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            border: '3px solid rgba(99,102,241,0.2)',
            borderTopColor: '#6366f1',
            animation: 'spin 0.8s linear infinite',
          }} />
          <p style={{ fontSize: '13px', color: '#6366f1', fontWeight: '600' }}>上传中…</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(118,75,162,0.08))',
            border: '1px solid rgba(99,102,241,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <FileUp size={18} style={{ color: '#6366f1' }} />
          </div>
          <div>
            <p style={{ fontSize: '13px', fontWeight: '600', color: '#374151' }}>
              {dragOver ? '放开上传' : '点击选择 PDF'}
            </p>
            <p style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              或拖拽文件到此处 · 单次最多 20 篇
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
