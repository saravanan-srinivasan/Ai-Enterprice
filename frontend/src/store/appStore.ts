// src/store/appStore.ts — Global application state

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { AgentType, QueryResponse } from '../utils/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agent_type?: AgentType
  confidence_score?: number
  sources?: QueryResponse['sources']
  tokens_used?: number
  latency_ms?: number
  cached?: boolean
  timestamp: string
  status: 'sending' | 'complete' | 'error'
}

interface AppState {
  // Session
  sessionId: string

  // Chat
  messages: ChatMessage[]
  isQuerying: boolean
  activeAgent: AgentType

  // UI
  activeTab: 'chat' | 'documents' | 'insights' | 'history'
  sidebarOpen: boolean

  // Settings
  topK: number
  includeSources: boolean
  showConfidence: boolean

  // Actions
  setActiveTab: (tab: AppState['activeTab']) => void
  setActiveAgent: (agent: AgentType) => void
  addMessage: (msg: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  setIsQuerying: (v: boolean) => void
  clearChat: () => void
  setSidebarOpen: (v: boolean) => void
  setTopK: (v: number) => void
  setIncludeSources: (v: boolean) => void
}

const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      sessionId: generateSessionId(),
      messages: [],
      isQuerying: false,
      activeAgent: 'query',
      activeTab: 'chat',
      sidebarOpen: true,
      topK: 5,
      includeSources: true,
      showConfidence: true,

      setActiveTab: (tab) => set({ activeTab: tab }),
      setActiveAgent: (agent) => set({ activeAgent: agent }),
      setIsQuerying: (v) => set({ isQuerying: v }),
      setSidebarOpen: (v) => set({ sidebarOpen: v }),
      setTopK: (v) => set({ topK: v }),
      setIncludeSources: (v) => set({ includeSources: v }),

      addMessage: (msg) =>
        set((s) => ({ messages: [...s.messages, msg] })),

      updateMessage: (id, patch) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
        })),

      clearChat: () =>
        set({ messages: [], sessionId: generateSessionId() }),
    }),
    {
      name: 'enterprise-ai-state',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({
        sessionId: s.sessionId,
        messages: s.messages,
        activeAgent: s.activeAgent,
        topK: s.topK,
        includeSources: s.includeSources,
      }),
    }
  )
)
