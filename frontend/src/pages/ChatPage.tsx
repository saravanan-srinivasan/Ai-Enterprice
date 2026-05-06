// src/pages/ChatPage.tsx
import React, { useRef, useEffect, useState, useCallback } from 'react'
import {
  Send, Trash2, Zap, BookOpen, Shield, FileCheck,
  ChevronDown, Copy, Check, RotateCcw, Info
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useAppStore, ChatMessage } from '../store/appStore'
import { api, AgentType } from '../utils/api'

const AGENT_META: Record<AgentType, { label: string; color: string; desc: string }> = {
  query:    { label: 'Query',    color: '#3b82f6', desc: 'Factual Q&A from knowledge base' },
  analysis: { label: 'Analysis', color: '#8b5cf6', desc: 'Pattern & insight extraction' },
  report:   { label: 'Report',   color: '#06b6d4', desc: 'Generate structured report' },
  action:   { label: 'Action',   color: '#f59e0b', desc: 'Decision support & recommendations' },
}

const STARTERS = [
  'What are the main causes of shipping delays in Q1 2024?',
  'Generate a logistics performance report for this quarter',
  'Analyze vendor risk factors from the vendor master data',
  'What decision should we make about Red Sea route alternatives?',
]

function ConfidenceBadge({ score }: { score: number }) {
  const color = score >= 0.8 ? '#10b981' : score >= 0.5 ? '#f59e0b' : '#ef4444'
  const label = score >= 0.8 ? 'High' : score >= 0.5 ? 'Medium' : 'Low'
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded"
      style={{ background: `${color}18`, color, border: `1px solid ${color}30` }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label} confidence · {Math.round(score * 100)}%
    </span>
  )
}

function SourcesPanel({ sources }: { sources: ChatMessage['sources'] }) {
  const [open, setOpen] = useState(false)
  if (!sources?.length) return null
  return (
    <div className="mt-3 border border-white/[0.07] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-[#6b7280] hover:bg-white/[0.03] transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <BookOpen size={11} />
          {sources.length} source{sources.length !== 1 ? 's' : ''} cited
        </span>
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-white/[0.06] divide-y divide-white/[0.04]">
          {sources.map((s) => (
            <div key={s.chunk_id} className="px-3 py-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-medium text-[#93c5fd] truncate max-w-[200px]">
                  {s.filename}
                </span>
                <span className="text-[10px] text-[#4b5563]">
                  {Math.round(s.relevance_score * 100)}% match
                  {s.page_number ? ` · p.${s.page_number}` : ''}
                </span>
              </div>
              <p className="text-[11px] text-[#6b7280] line-clamp-2">{s.content_preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const [copied, setCopied] = useState(false)
  const isUser = msg.role === 'user'

  const copy = () => {
    navigator.clipboard.writeText(msg.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-blue-500/15 border border-blue-500/20 rounded-2xl rounded-tr-sm px-4 py-3">
          <p className="text-sm text-[#dbeafe]">{msg.content}</p>
        </div>
      </div>
    )
  }

  if (msg.status === 'sending') {
    return (
      <div className="flex gap-3">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shrink-0 mt-0.5">
          <Zap size={13} className="text-white" />
        </div>
        <div className="glass rounded-2xl rounded-tl-sm px-4 py-3">
          <div className="flex gap-1.5 items-center h-5">
            {[0, 1, 2].map(i => (
              <span key={i} className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  const agentColor = msg.agent_type ? AGENT_META[msg.agent_type]?.color : '#3b82f6'

  return (
    <div className="flex gap-3 group">
      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: `${agentColor}22`, border: `1px solid ${agentColor}44` }}>
        <Zap size={13} style={{ color: agentColor }} />
      </div>
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {msg.agent_type && (
            <span className="text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: agentColor }}>
              {AGENT_META[msg.agent_type]?.label}
            </span>
          )}
          {msg.confidence_score !== undefined && (
            <ConfidenceBadge score={msg.confidence_score} />
          )}
          {msg.cached && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">
              ⚡ Cached
            </span>
          )}
          {msg.tokens_used ? (
            <span className="text-[10px] text-[#4b5563]">
              {msg.tokens_used.toLocaleString()} tokens · {msg.latency_ms}ms
            </span>
          ) : null}
        </div>

        {/* Content */}
        <div className={`glass rounded-2xl rounded-tl-sm px-4 py-3 ${msg.status === 'error' ? 'border-red-500/30' : ''}`}>
          {msg.status === 'error' ? (
            <p className="text-sm text-red-400">{msg.content}</p>
          ) : (
            <div className="prose-dark text-sm">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Sources */}
        <SourcesPanel sources={msg.sources} />

        {/* Actions */}
        <div className="flex gap-2 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={copy}
            className="flex items-center gap-1 text-[10px] text-[#4b5563] hover:text-[#9ca3af] transition-colors px-2 py-1 rounded">
            {copied ? <Check size={10} /> : <Copy size={10} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ChatPage() {
  const {
    messages, isQuerying, activeAgent,
    sessionId, topK, includeSources,
    addMessage, updateMessage, setIsQuerying, clearChat,
  } = useAppStore()

  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async (text?: string) => {
    const question = (text ?? input).trim()
    if (!question || isQuerying) return

    setInput('')
    setIsQuerying(true)

    const userMsgId = crypto.randomUUID()
    const asstMsgId = crypto.randomUUID()

    addMessage({
      id: userMsgId, role: 'user', content: question,
      timestamp: new Date().toISOString(), status: 'complete',
    })
    addMessage({
      id: asstMsgId, role: 'assistant', content: '',
      agent_type: activeAgent,
      timestamp: new Date().toISOString(), status: 'sending',
    })

    try {
      const res = await api.submitQuery({
        question, session_id: sessionId, agent_type: activeAgent,
        top_k: topK, include_sources: includeSources,
      })
      updateMessage(asstMsgId, {
        content: res.answer,
        status: 'complete',
        agent_type: res.agent_type,
        confidence_score: res.confidence_score,
        sources: res.sources,
        tokens_used: res.tokens_used,
        latency_ms: res.latency_ms,
        cached: res.cached,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An error occurred'
      updateMessage(asstMsgId, { content: msg, status: 'error' })
    } finally {
      setIsQuerying(false)
    }
  }, [input, isQuerying, activeAgent, sessionId, topK, includeSources, addMessage, updateMessage, setIsQuerying])

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] glass">
        <div>
          <h1 className="text-base font-semibold text-white">AI Knowledge Chat</h1>
          <p className="text-xs text-[#6b7280] mt-0.5">
            Agent: <span className="font-medium" style={{ color: AGENT_META[activeAgent].color }}>
              {AGENT_META[activeAgent].label}
            </span>
            <span className="mx-1.5 text-[#374151]">·</span>
            {AGENT_META[activeAgent].desc}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clearChat}
            className="flex items-center gap-1.5 text-xs text-[#6b7280] hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/[0.04] border border-transparent hover:border-white/[0.08]">
            <Trash2 size={13} />
            Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto text-center pt-12">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border border-blue-500/20 flex items-center justify-center mx-auto mb-4">
              <Zap size={24} className="text-blue-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">Enterprise Knowledge Assistant</h2>
            <p className="text-sm text-[#6b7280] mb-8">
              Ask questions about your logistics data, financial reports, vendor records, and operational logs.
            </p>
            <div className="grid grid-cols-1 gap-2 max-w-lg mx-auto">
              {STARTERS.map(s => (
                <button key={s} onClick={() => send(s)}
                  className="text-left glass rounded-xl px-4 py-3 text-sm text-[#9ca3af] hover:text-white hover:border-blue-500/20 transition-all duration-150 border border-white/[0.06] hover:bg-blue-500/[0.04]">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id} className="max-w-3xl mx-auto w-full animate-slide-up">
            <MessageBubble msg={msg} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 pb-6 pt-3 border-t border-white/[0.06]">
        <div className="max-w-3xl mx-auto">
          <div className="glass-elevated rounded-2xl border border-white/[0.08] focus-within:border-blue-500/30 transition-colors">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={`Ask the ${AGENT_META[activeAgent].label} agent anything…`}
              rows={1}
              disabled={isQuerying}
              className="w-full bg-transparent px-4 pt-4 pb-2 text-sm text-white placeholder:text-[#4b5563] resize-none outline-none min-h-[52px] max-h-32 overflow-y-auto"
              style={{ scrollbarWidth: 'none' }}
            />
            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-2">
                {(['query', 'analysis', 'report', 'action'] as AgentType[]).map(a => {
                  const { setActiveAgent } = useAppStore.getState()
                  return (
                    <button key={a} onClick={() => setActiveAgent(a)}
                      className={`text-[10px] px-2 py-1 rounded-md font-medium transition-all ${
                        activeAgent === a
                          ? 'text-white'
                          : 'text-[#4b5563] hover:text-[#9ca3af]'
                      }`}
                      style={activeAgent === a ? {
                        background: `${AGENT_META[a].color}20`,
                        color: AGENT_META[a].color,
                      } : {}}>
                      {a}
                    </button>
                  )
                })}
              </div>
              <button
                onClick={() => send()}
                disabled={!input.trim() || isQuerying}
                className="w-8 h-8 rounded-xl bg-blue-500 hover:bg-blue-400 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-colors shrink-0"
              >
                <Send size={14} className="text-white" />
              </button>
            </div>
          </div>
          <p className="text-center text-[10px] text-[#374151] mt-2">
            Shift+Enter for new line · Enter to send
          </p>
        </div>
      </div>
    </div>
  )
}
