import { useRef, useState } from 'react'
import { uploadPaper } from '../../lib/api.js'
import { useToast } from '../../contexts/ToastContext.jsx'

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
      if (result.success) {
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

  return (
    <div
      className={`mx-4 my-3 border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors
        ${dragOver ? 'border-accent bg-blue-50' : 'border-[#d1d5db] bg-[#f9fafb] hover:border-[#9ca3af]'}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={e => handleFiles(e.target.files)}
      />
      <p className="text-sm text-[#4b5563] font-medium">
        {uploading ? '上传中…' : '📄 点击选择 PDF，或拖拽到此处'}
      </p>
      <p className="text-xs text-[#9ca3af] mt-1">仅 PDF · 单次最多 20 篇</p>
    </div>
  )
}
