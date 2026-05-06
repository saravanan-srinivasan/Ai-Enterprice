// src/pages/DocumentsPage.tsx
import React, { useCallback, useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload, FileText, FileJson, File, Trash2,
  CheckCircle, XCircle, Clock, Loader2, AlertCircle,
  CloudUpload
} from 'lucide-react'
import { api, DocumentInfo, DocumentStatus } from '../utils/api'
import { formatDistanceToNow } from 'date-fns'

const EXT_ICON: Record<string, React.ReactNode> = {
  pdf:  <FileText size={14} className="text-red-400" />,
  json: <FileJson size={14} className="text-yellow-400" />,
  csv:  <FileText size={14} className="text-green-400" />,
  txt:  <File size={14} className="text-blue-400" />,
  log:  <File size={14} className="text-purple-400" />,
}

const STATUS_CONFIG: Record<DocumentStatus, { icon: React.ReactNode; color: string; label: string }> = {
  indexed:    { icon: <CheckCircle size={13} />, color: '#10b981', label: 'Indexed' },
  processing: { icon: <Loader2 size={13} className="animate-spin" />, color: '#3b82f6', label: 'Processing' },
  pending:    { icon: <Clock size={13} />, color: '#6b7280', label: 'Pending' },
  failed:     { icon: <XCircle size={13} />, color: '#ef4444', label: 'Failed' },
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DocumentCard({ doc, onDelete }: { doc: DocumentInfo; onDelete: (id: string) => void }) {
  const st = STATUS_CONFIG[doc.status]
  const ext = doc.doc_type
  return (
    <div className="glass rounded-xl border border-white/[0.06] hover:border-white/10 transition-all p-4 group">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center shrink-0">
          {EXT_ICON[ext] ?? <File size={14} className="text-[#6b7280]" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate" title={doc.original_name}>
            {doc.original_name}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-[10px] text-[#6b7280]">{formatBytes(doc.file_size_bytes)}</span>
            <span className="text-[#374151]">·</span>
            <span className="text-[10px] text-[#6b7280]">{doc.chunk_count} chunks</span>
            <span className="text-[#374151]">·</span>
            <span className="text-[10px] text-[#6b7280]">
              {formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-full"
            style={{ background: `${st.color}15`, color: st.color, border: `1px solid ${st.color}30` }}>
            {st.icon}
            {st.label}
          </span>
          <button
            onClick={() => onDelete(doc.id)}
            className="opacity-0 group-hover:opacity-100 text-[#4b5563] hover:text-red-400 transition-all p-1 rounded">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

function DropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(files)
  }, [onFiles])

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`
        relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
        transition-all duration-200
        ${dragging
          ? 'border-blue-500/60 bg-blue-500/[0.06]'
          : 'border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02]'}
      `}
    >
      <input ref={inputRef} type="file" multiple className="hidden"
        accept=".pdf,.txt,.json,.csv,.log"
        onChange={e => e.target.files && onFiles(Array.from(e.target.files))} />
      <div className="flex flex-col items-center gap-3">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
          dragging ? 'bg-blue-500/20' : 'bg-white/[0.04]'
        }`}>
          <CloudUpload size={22} className={dragging ? 'text-blue-400' : 'text-[#6b7280]'} />
        </div>
        <div>
          <p className="text-sm font-medium text-white">Drop files or click to upload</p>
          <p className="text-xs text-[#6b7280] mt-1">Supports PDF, TXT, JSON, CSV, LOG · Max 50MB</p>
        </div>
      </div>
    </div>
  )
}

interface UploadState {
  file: File
  status: 'uploading' | 'success' | 'error'
  message?: string
}

export default function DocumentsPage() {
  const qc = useQueryClient()
  const [uploads, setUploads] = useState<UploadState[]>([])

  const { data: docs, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.listDocuments({ limit: 100 }),
    refetchInterval: 5_000,
  })

  const { data: stats } = useQuery({
    queryKey: ['docStats'],
    queryFn: api.getDocumentStats,
    refetchInterval: 10_000,
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })

  const handleFiles = async (files: File[]) => {
    const newUploads: UploadState[] = files.map(f => ({ file: f, status: 'uploading' }))
    setUploads(prev => [...prev, ...newUploads])

    await Promise.all(
      files.map(async (file, idx) => {
        try {
          const res = await api.uploadDocument(file)
          setUploads(prev => prev.map((u, i) =>
            u.file === file ? { ...u, status: 'success', message: res.message } : u
          ))
          qc.invalidateQueries({ queryKey: ['documents'] })
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Upload failed'
          setUploads(prev => prev.map(u =>
            u.file === file ? { ...u, status: 'error', message: msg } : u
          ))
        }
      })
    )
  }

  const vectorStats = stats as Record<string, Record<string, unknown>> | undefined

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-6 py-5 border-b border-white/[0.06] glass">
        <h1 className="text-base font-semibold text-white">Document Ingestion</h1>
        <p className="text-xs text-[#6b7280] mt-0.5">Upload enterprise documents for AI knowledge indexing</p>
      </div>

      <div className="flex-1 p-6 max-w-4xl mx-auto w-full space-y-6">
        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Total Documents', value: docs?.length ?? 0 },
              { label: 'Indexed Chunks', value: (vectorStats?.vector_store?.total_vectors as number) ?? 0 },
              { label: 'Failed', value: (vectorStats?.documents_by_status?.failed as number) ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="glass rounded-xl p-4">
                <p className="text-2xl font-semibold text-white">{value.toLocaleString()}</p>
                <p className="text-xs text-[#6b7280] mt-1">{label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Upload zone */}
        <DropZone onFiles={handleFiles} />

        {/* Upload progress */}
        {uploads.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-[#6b7280] uppercase tracking-wider">Recent Uploads</p>
            {uploads.slice(-5).map((u, i) => (
              <div key={i} className="glass rounded-lg px-4 py-2.5 flex items-center gap-3">
                {EXT_ICON[u.file.name.split('.').pop() ?? ''] ?? <File size={13} />}
                <span className="text-sm text-white flex-1 truncate">{u.file.name}</span>
                {u.status === 'uploading' && <Loader2 size={14} className="text-blue-400 animate-spin" />}
                {u.status === 'success' && <CheckCircle size={14} className="text-green-400" />}
                {u.status === 'error' && (
                  <span className="flex items-center gap-1 text-[11px] text-red-400">
                    <AlertCircle size={13} /> {u.message}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Document list */}
        <div>
          <p className="text-xs font-medium text-[#6b7280] uppercase tracking-wider mb-3">
            Indexed Documents ({docs?.length ?? 0})
          </p>
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 size={20} className="text-[#6b7280] animate-spin" />
            </div>
          ) : docs?.length === 0 ? (
            <div className="text-center py-12 text-[#4b5563] text-sm">
              No documents ingested yet. Upload files above to get started.
            </div>
          ) : (
            <div className="space-y-2">
              {docs?.map(doc => (
                <DocumentCard key={doc.id} doc={doc}
                  onDelete={id => deleteMutation.mutate(id)} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
