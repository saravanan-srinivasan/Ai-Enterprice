// src/App.tsx
import React from 'react'
import { useAppStore } from './store/appStore'
import Sidebar from './components/Sidebar'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import InsightsPage from './pages/InsightsPage'
import HistoryPage from './pages/HistoryPage'

export default function App() {
  const { activeTab, sidebarOpen } = useAppStore()

  const pages: Record<string, React.ReactNode> = {
    chat:      <ChatPage />,
    documents: <DocumentsPage />,
    insights:  <InsightsPage />,
    history:   <HistoryPage />,
  }

  return (
    <div className="flex h-screen bg-[#0a0b0e] text-[#e8eaf0] overflow-hidden dot-grid">
      <Sidebar />
      <main
        className="flex-1 flex flex-col overflow-hidden transition-all duration-300"
        style={{ marginLeft: sidebarOpen ? 0 : 0 }}
      >
        <div className="flex-1 overflow-hidden animate-fade-in">
          {pages[activeTab] ?? <ChatPage />}
        </div>
      </main>
    </div>
  )
}
