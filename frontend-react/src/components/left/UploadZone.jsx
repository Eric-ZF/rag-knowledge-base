import { useRef, useState } from 'react'
import { uploadPaper } from '../../lib/api.js'
import { useToast } from '../../contexts/ToastContext.jsx'

export default function UploadZone() {
  const { addToast } = useToast()
  const inputRef = useRef()
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = async (files) => {
    const pdfs = Array.from(files).filter(f => f.name.endsWith('.pdf'))
    if (pdfs.length === 0) return addToast('仅支持 PDF 文件', 'warning')
    setUploading(true)
    setProgress(0)

    try {
      const formData = new FormData()
      pdfs.forEach(f => formData.append('files', f))
      formData.append('folder_id', localStorage.getItem('currentFolderId') || '')

      const result = await uploadPaper(formData)
      addToast(`${pdfs.length} 篇论文已提交索引`, 'success')
      // TODO: poll batch-status for progress
    } catch (e) {
      addToast(e.message || '上传失败', 'error')
    } finally {
      setUploading(false)
      setProgress(0)
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
        {uploading ? '上传中…' : '📄 点击选择 PDF 文件，或拖拽到此处'}
      </p>
      <p className="text-xs text-[#9ca3af] mt-1">仅支持 PDF · 单次最多 20 篇</p>
      {uploading && (
        <div className="mt-2">
          <div className="h-1 bg-[#e5e7eb] rounded overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}
