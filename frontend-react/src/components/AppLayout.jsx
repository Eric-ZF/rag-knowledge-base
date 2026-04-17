import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext.jsx'
import FolderTree from './left/FolderTree.jsx'
import UploadZone from './left/UploadZone.jsx'
import PaperList from './left/PaperList.jsx'
import QuotaBanner from './right/QuotaBanner.jsx'
import ChatPanel from './right/ChatPanel.jsx'
import ChatInput from './right/ChatInput.jsx'

export default function MainLayout() {
  const { userPhone, logout } = useAuth()
  const [currentFolderId, setCurrentFolderId] = useState(null)

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Header */}
      <header className="h-[52px] border-b border-[#e5e7eb] flex items-center px-5 gap-3 shrink-0">
        <h1 className="text-sm font-bold text-[#111827]">RAG 学术知识库</h1>
        <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 rounded-full font-medium">
          Phase 0
        </span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-[#6b7280]">{userPhone}</span>
          <button
            onClick={logout}
            className="text-xs text-[#9ca3af] hover:text-red-500 transition-colors bg-transparent border-none cursor-pointer"
          >
            退出
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-1/2 border-r border-[#e5e7eb] flex flex-col overflow-hidden">
          <FolderTree onSelectFolder={setCurrentFolderId} />
          <UploadZone folderId={currentFolderId} />
          <PaperList folderId={currentFolderId} />
        </div>

        {/* Right panel */}
        <div className="w-1/2 flex flex-col overflow-hidden">
          <QuotaBanner />
          <div className="flex-1 overflow-hidden flex flex-col">
            <ChatPanel folderIds={currentFolderId ? [currentFolderId] : []} />
            <ChatInput />
          </div>
        </div>
      </div>
    </div>
  )
}
