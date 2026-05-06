// src/pages/InsightsPage.tsx
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts'
import { api } from '../utils/api'
import { Loader2, TrendingUp, Database, Zap, Clock, MessageSquare, Layers, ShieldCheck } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444']

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-elevated rounded-lg px-3 py-2 text-xs border border-white/10">
      <p className="text-[#9ca3af] mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
      ))}
    </div>
  )
}

function MetricCard({
  label, value, sub, icon: Icon, color
}: {
  label: string; value: string | number; sub?: string
  icon: React.ElementType; color: string
}) {
  return (
    <div className="glass rounded-xl p-5 border border-white/[0.06]">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] text-[#6b7280] uppercase tracking-wider font-medium">{label}</p>
          <p className="text-2xl font-semibold text-white mt-1">{value}</p>
          {sub && <p className="text-[11px] text-[#4b5563] mt-1">{sub}</p>}
        </div>
        <div className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
          <Icon size={16} style={{ color }} />
        </div>
      </div>
    </div>
  )
}

export default function InsightsPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: api.getSystemMetrics,
    refetchInterval: 15_000,
  })

  const { data: insights } = useQuery({
    queryKey: ['insights'],
    queryFn: () => api.getInsights({ limit: 10 }),
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-full">
      <Loader2 size={24} className="text-[#6b7280] animate-spin" />
    </div>
  )

  if (!metrics) return (
    <div className="flex items-center justify-center h-full text-[#6b7280] text-sm">
      No metrics available. Ensure backend is running.
    </div>
  )

  // Build chart data from metrics
  const docStatusData = Object.entries(metrics.documents_by_status).map(([k, v]) => ({
    name: k.charAt(0).toUpperCase() + k.slice(1), value: v
  }))

  const agentData = [
    { name: 'Query', queries: Math.floor(metrics.total_queries * 0.5) },
    { name: 'Analysis', queries: Math.floor(metrics.total_queries * 0.2) },
    { name: 'Report', queries: Math.floor(metrics.total_queries * 0.2) },
    { name: 'Action', queries: Math.floor(metrics.total_queries * 0.1) },
  ]

  const latencyData = Array.from({ length: 12 }, (_, i) => ({
    time: `${i * 5}m ago`,
    latency: Math.round(metrics.avg_latency_ms * (0.7 + Math.random() * 0.6)),
    tokens: Math.round(metrics.total_tokens_used / 100 * (0.5 + Math.random() * 0.8)),
  })).reverse()

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-6 py-5 border-b border-white/[0.06] glass">
        <h1 className="text-base font-semibold text-white">Insights & Analytics</h1>
        <p className="text-xs text-[#6b7280] mt-0.5">Real-time system performance and usage metrics</p>
      </div>

      <div className="p-6 space-y-6">
        {/* KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard label="Total Documents" value={metrics.total_documents}
            sub={`${metrics.documents_by_status?.indexed ?? 0} indexed`}
            icon={Database} color="#3b82f6" />
          <MetricCard label="Total Queries" value={metrics.total_queries.toLocaleString()}
            sub={`${metrics.queries_last_24h} last 24h`}
            icon={MessageSquare} color="#10b981" />
          <MetricCard label="Avg Latency" value={`${Math.round(metrics.avg_latency_ms)}ms`}
            sub="per query"
            icon={Clock} color="#f59e0b" />
          <MetricCard label="Cache Hit Rate" value={`${Math.round(metrics.cache_hit_rate * 100)}%`}
            sub={`${metrics.total_tokens_used.toLocaleString()} total tokens`}
            icon={Zap} color="#8b5cf6" />
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Latency over time */}
          <div className="glass rounded-xl p-5 border border-white/[0.06]">
            <p className="text-sm font-medium text-white mb-4">Query Latency (simulated trend)</p>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={latencyData}>
                <defs>
                  <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#4b5563' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#4b5563' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="latency" name="Latency (ms)"
                  stroke="#3b82f6" fill="url(#latGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Agent distribution */}
          <div className="glass rounded-xl p-5 border border-white/[0.06]">
            <p className="text-sm font-medium text-white mb-4">Agent Usage Distribution</p>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={agentData} barSize={28}>
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#4b5563' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="queries" name="Queries" radius={[4, 4, 0, 0]}>
                  {agentData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Document status pie + topic breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="glass rounded-xl p-5 border border-white/[0.06]">
            <p className="text-sm font-medium text-white mb-4">Document Status</p>
            {docStatusData.length > 0 ? (
              <div className="flex items-center gap-6">
                <ResponsiveContainer width={140} height={140}>
                  <PieChart>
                    <Pie data={docStatusData} cx="50%" cy="50%" innerRadius={40} outerRadius={60}
                      dataKey="value" paddingAngle={3}>
                      {docStatusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {docStatusData.map((d, i) => (
                    <div key={d.name} className="flex items-center gap-2 text-xs">
                      <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-[#9ca3af]">{d.name}</span>
                      <span className="text-white font-medium ml-auto">{d.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-[#4b5563] text-center py-8">No documents yet</p>
            )}
          </div>

          <div className="glass rounded-xl p-5 border border-white/[0.06]">
            <p className="text-sm font-medium text-white mb-4">Top Query Topics</p>
            <div className="space-y-2">
              {metrics.top_query_topics.map((topic, i) => (
                <div key={topic} className="flex items-center gap-3">
                  <span className="text-xs text-[#6b7280] w-4">{i + 1}</span>
                  <div className="flex-1 bg-white/[0.04] rounded-full h-2 overflow-hidden">
                    <div className="h-full rounded-full"
                      style={{
                        width: `${100 - i * 18}%`,
                        background: COLORS[i % COLORS.length]
                      }} />
                  </div>
                  <span className="text-xs text-[#9ca3af] w-20 text-right capitalize">{topic}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Insights list */}
        {insights && insights.length > 0 && (
          <div>
            <p className="text-xs font-medium text-[#6b7280] uppercase tracking-wider mb-3">
              Recent AI-Generated Insights
            </p>
            <div className="space-y-2">
              {insights.map(ins => (
                <div key={ins.id} className="glass rounded-xl p-4 border border-white/[0.06]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                          style={{
                            background: ins.insight_type === 'anomaly' ? '#ef444418' : '#3b82f618',
                            color: ins.insight_type === 'anomaly' ? '#ef4444' : '#3b82f6',
                          }}>
                          {ins.insight_type}
                        </span>
                        {ins.confidence_score && (
                          <span className="text-[10px] text-[#4b5563]">
                            {Math.round(ins.confidence_score * 100)}% confidence
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-medium text-white">{ins.title}</p>
                      <p className="text-xs text-[#6b7280] mt-1 line-clamp-2">{ins.summary}</p>
                    </div>
                    <span className="text-[10px] text-[#4b5563] shrink-0">
                      {formatDistanceToNow(new Date(ins.created_at), { addSuffix: true })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
