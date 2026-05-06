// src/utils/api.ts — Typed API client for the Enterprise AI backend

import axios, { AxiosInstance, AxiosResponse } from 'axios'

// ── Types ────────────────────────────────────────────────────────────────────

export type AgentType = 'query' | 'analysis' | 'report' | 'action'
export type DocumentStatus = 'pending' | 'processing' | 'indexed' | 'failed'
export type QueryStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface SourceDocument {
  doc_id: string
  filename: string
  chunk_id: string
  content_preview: string
  relevance_score: number
  page_number?: number
}

export interface QueryRequest {
  question: string
  session_id: string
  agent_type: AgentType
  top_k: number
  include_sources: boolean
  filters?: Record<string, string>
}

export interface QueryResponse {
  query_id: string
  session_id: string
  question: string
  answer: string
  agent_type: AgentType
  status: QueryStatus
  sources: SourceDocument[]
  confidence_score: number
  tokens_used: number
  latency_ms: number
  cached: boolean
  reasoning_steps?: string[]
  created_at: string
}

export interface QueryHistoryItem {
  id: string
  session_id: string
  question: string
  answer?: string
  agent_type: AgentType
  status: QueryStatus
  confidence_score?: number
  tokens_used: number
  latency_ms: number
  cached: boolean
  created_at: string
}

export interface DocumentInfo {
  id: string
  filename: string
  original_name: string
  doc_type: string
  file_size_bytes: number
  status: DocumentStatus
  chunk_count: number
  created_at: string
  indexed_at?: string
}

export interface DocumentUploadResponse {
  document_id: string
  filename: string
  status: DocumentStatus
  message: string
}

export interface SystemMetrics {
  total_documents: number
  total_queries: number
  avg_latency_ms: number
  cache_hit_rate: number
  total_tokens_used: number
  documents_by_status: Record<string, number>
  queries_last_24h: number
  top_query_topics: string[]
}

export interface InsightSummary {
  id: string
  insight_type: string
  title: string
  summary: string
  confidence_score?: number
  tags: string[]
  created_at: string
}

export interface HealthStatus {
  status: 'healthy' | 'degraded'
  checks: Record<string, unknown>
  version: string
}

// ── Axios instance ────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL || ''

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000, // 2-minute timeout for long agent completions
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach request ID
client.interceptors.request.use(config => {
  config.headers['X-Request-ID'] = crypto.randomUUID()
  return config
})

// Response interceptor — unwrap data
client.interceptors.response.use(
  r => r,
  err => {
    const detail = err.response?.data?.detail || err.response?.data?.error || err.message
    return Promise.reject(new Error(detail))
  }
)

// ── API Methods ───────────────────────────────────────────────────────────────

export const api = {
  // Queries
  async submitQuery(req: QueryRequest): Promise<QueryResponse> {
    const r: AxiosResponse<QueryResponse> = await client.post('/api/v1/query', req)
    return r.data
  },

  async getHistory(params?: {
    session_id?: string
    agent_type?: AgentType
    limit?: number
    offset?: number
  }): Promise<QueryHistoryItem[]> {
    const r: AxiosResponse<QueryHistoryItem[]> = await client.get('/api/v1/history', { params })
    return r.data
  },

  async getQueryById(id: string): Promise<QueryHistoryItem> {
    const r: AxiosResponse<QueryHistoryItem> = await client.get(`/api/v1/history/${id}`)
    return r.data
  },

  // Documents
  async uploadDocument(file: File, sourceTag?: string): Promise<DocumentUploadResponse> {
    const form = new FormData()
    form.append('file', file)
    if (sourceTag) form.append('source_tag', sourceTag)
    const r: AxiosResponse<DocumentUploadResponse> = await client.post('/api/v1/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return r.data
  },

  async listDocuments(params?: { status?: DocumentStatus; limit?: number }): Promise<DocumentInfo[]> {
    const r: AxiosResponse<DocumentInfo[]> = await client.get('/api/v1/documents', { params })
    return r.data
  },

  async deleteDocument(docId: string): Promise<{ status: string }> {
    const r = await client.delete(`/api/v1/documents/${docId}`)
    return r.data
  },

  async getDocumentStats(): Promise<Record<string, unknown>> {
    const r = await client.get('/api/v1/documents/stats')
    return r.data
  },

  // Insights & Metrics
  async getInsights(params?: { insight_type?: string; limit?: number }): Promise<InsightSummary[]> {
    const r: AxiosResponse<InsightSummary[]> = await client.get('/api/v1/insights', { params })
    return r.data
  },

  async getSystemMetrics(): Promise<SystemMetrics> {
    const r: AxiosResponse<SystemMetrics> = await client.get('/api/v1/insights/metrics')
    return r.data
  },

  // Health
  async getHealth(): Promise<HealthStatus> {
    const r: AxiosResponse<HealthStatus> = await client.get('/health/ready')
    return r.data
  },
}
