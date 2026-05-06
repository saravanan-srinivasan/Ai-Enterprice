// src/pages/HistoryPage.tsx
import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, AgentType, QueryHistoryItem } from '../utils/api'
import { formatDistanceToNow, format } from 'date-fns'
import { Loader2, ChevronDown, ChevronRight, Zap, CheckCircle, XCircle, Clock } from 'lucide-react'

const AGENT_COLORS: Record<AgentType, string> = {
  query:    '#3b82f6',
  analysis: '#8b5cf6',
  report:   '#06b6d4',
  action:   '#f59e0b',
}

function HistoryRow({ item }: { item: QueryHistoryItem }) {
  const [expanded, setExpanded] = useState(false)
  const color = AGENT_COLORS[item.agent_type]

  return (
    <div className="glass rounded-xl border border-white/[0.06] overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
          <Zap size={12} style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white truncate">{item.question}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-medium capitalize" style={{ color }}>{item.agent_type}</span>
            <span className="text-[#374151]">·</span>
            <span className="text-[10px] text-[#4b5563]">
              {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
            </span>
            {item.cached && (
              <span className="text-[10px] text-green-400">⚡ cached</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {item.confidence_score !== undefined && (
            <span className="text-[11px] px-2 py-0.5 rounded-full"
              style={{
                background: item.confidence_score >= 0.7 ? '#10b98118' : '#f59e0b18',
                color: item.confidence_score >= 0.7 ? '#10b981' : '#f59e0b',
              }}>
              {Math.round(item.confidence_score * 100)}%
            </span>
          )}
          <span className="text-[10px] text-[#4b5563]">{item.latency_ms}ms</span>
          {item.status === 'completed'
            ? <CheckCircle size={13} className="text-green-500" />
            : item.status === 'failed'
            ? <XCircle size={13} className="text-red-500" />
            : <Clock size={13} className="text-[#6b7280]" />
          }
          {expanded ? <ChevronDown size={13} className="text-[#4b5563]" /> : <ChevronRight size={13} className="text-[#4b5563]" />}
        </div>
      </button>

      {expanded && item.answer && (
        <div className="border-t border-white/[0.06] px-4 py-4 bg-white/[0.01]">
          <div className="flex items-center gap-4 mb-3 text-[10px] text-[#4b5563]">
            <span>ID: <code className="text-[#6b7280] font-mono">{item.id.slice(0, 8)}…</code></span>
            <span>Session: <code className="text-[#6b7280] font-mono">{item.session_id.slice(0, 12)}…</code></span>
            <span>Tokens: {item.tokens_used.toLocaleString()}</span>
            <span>{format(new Date(item.created_at), 'MMM d, yyyy HH:mm:ss')}</span>
          </div>
          <div className="text-sm text-[#9ca3af] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
            {item.answer}
          </div>
        </div>
      )}
    </div>
  )
}

export default function HistoryPage() {
  const [agentFilter, setAgentFilter] = useState<AgentType | 'all'>('all')

  const { data: history, isLoading } = useQuery({
    queryKey: ['history', agentFilter],
    queryFn: () => api.getHistory({
      agent_type: agentFilter === 'all' ? undefined : agentFilter,
      limit: 100,
    }),
    refetchInterval: 10_000,
  })

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-6 py-5 border-b border-white/[0.06] glass">
        <h1 className="text-base font-semibold text-white">Query History</h1>
        <p className="text-xs text-[#6b7280] mt-0.5">Complete audit log of all AI queries</p>
      </div>

      <div className="p-6 max-w-4xl mx-auto w-full space-y-4">
        {/* Filter bar */}
        <div className="flex items-center gap-2">
          {(['all', 'query', 'analysis', 'report', 'action'] as const).map(a => (
            <button key={a} onClick={() => setAgentFilter(a)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${
                agentFilter === a
                  ? 'text-white'
                  : 'text-[#6b7280] hover:text-[#9ca3af] bg-transparent'
              }`}
              style={agentFilter === a && a !== 'all' ? {
                background: `${AGENT_COLORS[a]}20`,
                color: AGENT_COLORS[a],
                border: `1px solid ${AGENT_COLORS[a]}30`,
              } : agentFilter === a ? {
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.12)',
              } : { border: '1px solid transparent' }}>
              {a === 'all' ? 'All Agents' : a.charAt(0).toUpperCase() + a.slice(1)}
            </button>
          ))}
          <span className="ml-auto text-xs text-[#4b5563]">
            {history?.length ?? 0} records
          </span>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 size={20} className="text-[#6b7280] animate-spin" />
          </div>
        ) : history?.length === 0 ? (
          <div className="text-center py-12 text-[#4b5563] text-sm">
            No queries recorded yet. Start chatting to see history here.
          </div>
        ) : (
          <div className="space-y-2">
            {history?.map(item => (
              <HistoryRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
