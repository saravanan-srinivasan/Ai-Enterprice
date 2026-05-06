// src/components/Sidebar.tsx
import React from 'react'
import {
  MessageSquare, FileText, BarChart3, Clock,
  Brain, ChevronLeft, ChevronRight, Zap, Settings
} from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '../utils/api'

const NAV = [
  { id: 'chat',      icon: MessageSquare, label: 'AI Chat',     badge: null },
  { id: 'documents', icon: FileText,      label: 'Documents',   badge: null },
  { id: 'insights',  icon: BarChart3,     label: 'Insights',    badge: null },
  { id: 'history',   icon: Clock,         label: 'Query Log',   badge: null },
] as const

const AGENT_COLORS: Record<string, string> = {
  query:    'bg-blue-500/20 text-blue-400 border-blue-500/30',
  analysis: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  report:   'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  action:   'bg-amber-500/20 text-amber-400 border-amber-500/30',
}

export default function Sidebar() {
  const { activeTab, setActiveTab, sidebarOpen, setSidebarOpen, activeAgent, setActiveAgent } = useAppStore()

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30_000,
    retry: false,
  })

  const isOnline = health?.status === 'healthy'

  return (
    <aside
      className="flex flex-col glass border-r border-white/[0.06] transition-all duration-300 shrink-0"
      style={{ width: sidebarOpen ? 220 : 64 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/[0.06]">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shrink-0">
          <Brain size={16} className="text-white" />
        </div>
        {sidebarOpen && (
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-white leading-tight truncate">Enterprise AI</p>
            <p className="text-[10px] text-[#6b7280] leading-tight">Knowledge Assistant</p>
          </div>
        )}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="ml-auto text-[#6b7280] hover:text-white transition-colors shrink-0"
        >
          {sidebarOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV.map(({ id, icon: Icon, label }) => {
          const active = activeTab === id
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                transition-all duration-150 group
                ${active
                  ? 'bg-blue-500/15 text-blue-400 border border-blue-500/20'
                  : 'text-[#6b7280] hover:text-white hover:bg-white/[0.04]'}
              `}
            >
              <Icon size={16} className="shrink-0" />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </button>
          )
        })}

        {/* Agent Selector */}
        {sidebarOpen && (
          <div className="pt-4 pb-1">
            <p className="px-3 text-[10px] font-semibold text-[#4b5563] uppercase tracking-widest mb-2">
              Active Agent
            </p>
            {(['query', 'analysis', 'report', 'action'] as const).map(agent => (
              <button
                key={agent}
                onClick={() => setActiveAgent(agent)}
                className={`
                  w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium mb-1
                  border transition-all duration-150
                  ${activeAgent === agent
                    ? AGENT_COLORS[agent]
                    : 'text-[#6b7280] border-transparent hover:bg-white/[0.03]'}
                `}
              >
                <Zap size={11} />
                <span className="capitalize">{agent}</span>
              </button>
            ))}
          </div>
        )}
      </nav>

      {/* Status footer */}
      <div className="px-3 py-3 border-t border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className={`status-dot ${isOnline ? 'online' : 'error'}`} />
          {sidebarOpen && (
            <span className="text-[11px] text-[#6b7280]">
              {isOnline ? 'All systems operational' : 'Backend offline'}
            </span>
          )}
        </div>
      </div>
    </aside>
  )
}
