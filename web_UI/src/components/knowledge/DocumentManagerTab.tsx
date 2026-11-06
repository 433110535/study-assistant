import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  fetchKnowledgeDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
} from '@/lib/api-client';
import { KnowledgeStatsResponse } from '@/types/knowledge';
import {
  Upload,
  FileText,
  Trash2,
  RotateCcw,
  Sparkles,
  AlertCircle,
  Database,
  Layers,
} from 'lucide-react';

interface DocumentManagerTabProps {
  onIndexUpdated?: (totalDocs: number) => void;
}

export const DocumentManagerTab: React.FC<DocumentManagerTabProps> = ({
  onIndexUpdated,
}) => {
  const [data, setData] = useState<KnowledgeStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [telemetryMessage, setTelemetryMessage] = useState<string | null>(null);

  // Upload Form State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState('');
  const [docSubject, setDocSubject] = useState('未分类');
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchKnowledgeDocuments('student');
      setData(res);
      if (onIndexUpdated) onIndexUpdated(res.total_documents);
    } catch (err: any) {
      console.error('Failed to load documents', err);
    } finally {
      setLoading(false);
    }
  }, [onIndexUpdated]);

  useEffect(() => {
    let active = true;
    fetchKnowledgeDocuments('student')
      .then((res) => {
        if (active) {
          setData(res);
          if (onIndexUpdated) onIndexUpdated(res.total_documents);
        }
      })
      .catch((err) => {
        if (active) console.error('Failed to load documents', err);
      });
    return () => {
      active = false;
    };
  }, [onIndexUpdated]);

  const handleFileSelect = (file: File) => {
    setErrorMessage(null);
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMessage('ILLEGAL_FILE_TYPE: ONLY_PDF_DOCUMENTS_ACCEPTED (.pdf)');
      return;
    }
    setSelectedFile(file);
    if (!docTitle.trim()) {
      // Auto-strip .pdf suffix
      const strippedTitle = file.name.replace(/\.pdf$/i, '');
      setDocTitle(strippedTitle);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage('PLEASE_SELECT_OR_DROP_A_PDF_FILE');
      return;
    }

    setUploading(true);
    setErrorMessage(null);
    setTelemetryMessage('[INGESTING_PDF -> CHUNKING -> DASHSCOPE_EMBEDDING -> FAISS_INDEXING...]');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('title', docTitle.trim() || selectedFile.name.replace(/\.pdf$/i, ''));
      formData.append('subject', docSubject.trim() || '未分类');

      await uploadKnowledgeDocument(formData);
      setTelemetryMessage(`INDEX_INGESTION_SUCCESS: [${selectedFile.name}]`);
      setTimeout(() => setTelemetryMessage(null), 3000);

      // Reset form
      setSelectedFile(null);
      setDocTitle('');
      if (fileInputRef.current) fileInputRef.current.value = '';

      await loadDocuments();
    } catch (err: any) {
      setErrorMessage(`INGESTION_ERROR: ${err.message}`);
      setTelemetryMessage(null);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm(`确认从知识库与向量索引中删除文档 [${docId}] 吗？`)) return;
    setDeletingId(docId);
    try {
      await deleteKnowledgeDocument(docId, 'student');
      await loadDocuments();
    } catch (err: any) {
      alert(`删除失败: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Telemetry Flash Banner */}
      {telemetryMessage && (
        <div className="px-4 py-2 bg-[#FAFF69]/10 border border-[#FAFF69] text-[#FAFF69] text-xs font-mono flex items-center justify-between animate-in fade-in duration-200">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-[#FAFF69] animate-pulse" />
            <span>{telemetryMessage}</span>
          </div>
          <span className="text-[10px] text-neutral-400">[FAISS_VECTOR_ENGINE]</span>
        </div>
      )}

      {/* Error Message */}
      {errorMessage && (
        <div className="px-4 py-2 bg-red-950/30 border border-red-500 text-red-400 text-xs font-mono flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* FAISS Telemetry Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider flex items-center space-x-1">
            <FileText className="w-3 h-3 text-[#FAFF69]" />
            <span>TOTAL_DOCUMENTS</span>
          </div>
          <div className="text-xl font-bold text-white mt-1">
            {data?.total_documents ?? 0}
          </div>
        </div>

        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider flex items-center space-x-1">
            <Layers className="w-3 h-3 text-[#4ADE80]" />
            <span>TOTAL_CHUNKS</span>
          </div>
          <div className="text-xl font-bold text-[#4ADE80] mt-1">
            {data?.total_chunks ?? 0}
          </div>
        </div>

        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider flex items-center space-x-1">
            <Database className="w-3 h-3 text-[#FAFF69]" />
            <span>INDEX_ENGINE</span>
          </div>
          <div className="text-sm font-bold text-neutral-200 mt-1 uppercase">
            {data?.index_version ?? 'FAISS_V1'}
          </div>
        </div>

        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider">
            STORAGE_ENGINE
          </div>
          <div className="text-sm font-bold text-neutral-200 mt-1">
            SQLITE + FAISS DUAL-WRITE
          </div>
        </div>
      </div>

      {/* PDF Drag-and-Drop Ingestion Card */}
      <form
        onSubmit={handleUpload}
        className="p-5 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-4"
      >
        <div className="flex items-center justify-between border-b border-[rgba(65,65,65,0.8)] pb-2">
          <span className="text-xs text-[#FAFF69] font-bold flex items-center space-x-1.5">
            <Upload className="w-4 h-4" />
            <span>[DOCUMENT_INGESTION_PIPELINE / 课件与教材入库]</span>
          </span>
          <span className="text-[10px] text-neutral-500">
            支持拖拽上传 PDF，自动切片分词并调用 DashScope 向量化
          </span>
        </div>

        {/* Drag-and-Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`p-6 border-2 border-dashed transition-colors flex flex-col items-center justify-center space-y-2 cursor-pointer ${
            isDragging
              ? 'border-[#FAFF69] bg-[#FAFF69]/10'
              : 'border-[rgba(65,65,65,0.8)] bg-black hover:border-neutral-400'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileSelect(e.target.files[0]);
              }
            }}
          />
          <Upload className="w-6 h-6 text-neutral-400" />
          <div className="text-xs text-neutral-200 font-bold">
            {selectedFile ? (
              <span className="text-[#FAFF69]">
                SELECTED: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </span>
            ) : (
              <span>DRAG_AND_DROP_PDF_HERE_OR_CLICK_TO_BROWSE</span>
            )}
          </div>
          <div className="text-[10px] text-neutral-500">
            仅支持合法的 .pdf 格式文档
          </div>
        </div>

        {/* Title and Subject Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              DOCUMENT_TITLE / 文档标题 (自动剥离 .pdf 后缀):
            </label>
            <input
              type="text"
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              placeholder="例如：高等数学第七版上册"
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            />
          </div>

          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              SUBJECT / 学科分类:
            </label>
            <input
              type="text"
              value={docSubject}
              onChange={(e) => setDocSubject(e.target.value)}
              placeholder="例如：高等数学 / 线性代数"
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            />
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center justify-end space-x-3 pt-2 border-t border-[rgba(65,65,65,0.8)]">
          <button
            type="submit"
            disabled={!selectedFile || uploading}
            className="px-5 py-2 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 disabled:opacity-50 flex items-center space-x-1.5 cursor-pointer"
          >
            {uploading ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>INDEXING_INTO_FAISS...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>START_VECTOR_INGESTION</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Indexed Documents Table */}
      <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
        <div className="p-3 border-b border-[rgba(65,65,65,0.8)] flex items-center justify-between">
          <div className="text-xs text-white font-bold flex items-center space-x-2">
            <span>INDEXED_DOCUMENT_RECORDS</span>
            <span className="text-neutral-500 font-normal">
              ({data?.documents?.length ?? 0} RECORDS)
            </span>
          </div>
          <button
            type="button"
            onClick={loadDocuments}
            className="p-1 border border-[rgba(65,65,65,0.8)] text-neutral-400 hover:text-white"
            title="Reload Documents"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-neutral-500">
            [QUERYING_DOCUMENT_RECORDS...]
          </div>
        ) : !data?.documents || data.documents.length === 0 ? (
          <div className="p-8 text-center text-neutral-500 space-y-1">
            <div>NO_DOCUMENTS_IN_INDEX</div>
            <p className="text-xs text-neutral-600">
              请在上方拖入课程教材或知识大纲 PDF 文档启动向量切片建库。
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[rgba(65,65,65,0.8)]">
            {data.documents.map((doc) => {
              const docId = doc.doc_id || doc.id || '';
              const isDeleting = deletingId === docId;

              return (
                <div
                  key={docId}
                  className="p-3 hover:bg-white/[0.02] transition-colors flex items-center justify-between gap-3"
                >
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <FileText className="w-4 h-4 text-[#FAFF69] flex-shrink-0" />
                    <div className="min-w-0">
                      <div className="text-xs text-white font-bold truncate">
                        {doc.title}
                      </div>
                      <div className="text-[10px] text-neutral-500 space-x-2">
                        <span>[ID: {docId}]</span>
                        <span>•</span>
                        <span>[SUBJECT: {doc.subject || '未分类'}]</span>
                        <span>•</span>
                        <span>[CHUNKS: {doc.chunks}]</span>
                        <span>•</span>
                        <span>
                          [INDEXED: {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'N/A'}]
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    disabled={isDeleting}
                    onClick={() => handleDelete(docId)}
                    className="px-2.5 py-1 border border-neutral-700 text-neutral-400 hover:border-red-500 hover:text-red-400 text-xs flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>DELETE</span>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
