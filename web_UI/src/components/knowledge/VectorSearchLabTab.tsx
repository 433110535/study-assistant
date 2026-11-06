import React, { useState } from 'react';
import { searchKnowledge } from '@/lib/api-client';
import { KnowledgeSearchResult } from '@/types/knowledge';
import {
  Search,
  RotateCcw,
  Sparkles,
  ArrowRight,
  AlertTriangle,
  FileText,
  SlidersHorizontal,
} from 'lucide-react';

interface VectorSearchLabTabProps {
  totalDocuments: number;
  onSendQueryToQa?: (query: string) => void;
  onSwitchToManager?: () => void;
}

export const VectorSearchLabTab: React.FC<VectorSearchLabTabProps> = ({
  totalDocuments,
  onSendQueryToQa,
  onSwitchToManager,
}) => {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [subjectFilter, setSubjectFilter] = useState('');
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setHasSearched(true);
    try {
      const res = await searchKnowledge(query.trim(), topK, subjectFilter.trim() || undefined);
      setResults(res.results || []);
    } catch (err: any) {
      alert(`搜索失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Empty Index Guard Banner */}
      {totalDocuments === 0 && (
        <div className="p-4 border border-[#FAFF69] bg-[#FAFF69]/5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-[#FAFF69] text-xs font-bold">
              <AlertTriangle className="w-4 h-4" />
              <span>FAISS_INDEX_EMPTY: PLEASE_UPLOAD_PDF_IN_TAB_1_FIRST</span>
            </div>
            {onSwitchToManager && (
              <button
                type="button"
                onClick={onSwitchToManager}
                className="px-3 py-1 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 flex items-center space-x-1"
              >
                <span>GO_TO_TAB_1_UPLOAD</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <p className="text-xs text-neutral-400">
            向量索引库目前没有任何切片。请先前往文档管理工作台上传教材 PDF 进行切片分词和嵌入计算。
          </p>
        </div>
      )}

      {/* Query Formulation Workbench */}
      <form
        onSubmit={handleSearch}
        className="p-5 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-4"
      >
        <div className="flex items-center justify-between border-b border-[rgba(65,65,65,0.8)] pb-2">
          <span className="text-xs text-[#FAFF69] font-bold flex items-center space-x-1.5">
            <Search className="w-4 h-4" />
            <span>[VECTOR_SIMILARITY_BENCH / 语义向量检索实验室]</span>
          </span>
          <span className="text-[10px] text-neutral-500">
            基于 DashScope Cosine 相似度进行 FAISS 倒排检索
          </span>
        </div>

        <div>
          <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
            QUERY_STRING / 检索测试语句:
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="例如：拉格朗日中值定理的前提条件是什么？"
            className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-3 py-2 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold flex items-center space-x-1">
              <SlidersHorizontal className="w-3 h-3" />
              <span>TOP_K_RESULTS / 召回切片数:</span>
            </label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            >
              <option value={1}>Top 1 (精细单条)</option>
              <option value={3}>Top 3 (标准模式)</option>
              <option value={5}>Top 5 (高召回推荐)</option>
              <option value={8}>Top 8 (广度探索)</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              SUBJECT_FILTER / 学科过滤 (可选):
            </label>
            <input
              type="text"
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
              placeholder="留空检索全部学科，或指定如：高等数学"
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-[rgba(65,65,65,0.8)]">
          {query.trim() && onSendQueryToQa && (
            <button
              type="button"
              onClick={() => onSendQueryToQa(query.trim())}
              className="px-3 py-1.5 border border-[#FAFF69] text-[#FAFF69] hover:bg-[#FAFF69] hover:text-black text-xs font-bold uppercase tracking-wider flex items-center space-x-1"
            >
              <span>SEND_QUERY_TO_RAG_QA -&gt;</span>
            </button>
          )}

          <div className="flex items-center space-x-2 ml-auto">
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-5 py-2 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 disabled:opacity-50 flex items-center space-x-1.5 cursor-pointer"
            >
              {loading ? (
                <>
                  <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                  <span>SEARCHING_FAISS...</span>
                </>
              ) : (
                <>
                  <Search className="w-3.5 h-3.5" />
                  <span>RUN_SIMILARITY_SEARCH</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Results Deck */}
      {hasSearched && (
        <div className="space-y-3">
          <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] flex items-center justify-between">
            <span className="text-xs text-white font-bold flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-[#FAFF69]" />
              <span>SEARCH_HIT_RESULTS ({results.length} CHUNKS RETRIEVED)</span>
            </span>
            <span className="text-[10px] text-neutral-500">
              按相似度得分从高到低排序
            </span>
          </div>

          {results.length === 0 ? (
            <div className="p-8 text-center border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-500">
              NO_RELEVANT_CHUNKS_FOUND
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((res, index) => {
                const rawScore = res.similarity ?? res.score ?? 0;
                const formattedScore = Number(rawScore).toFixed(4);
                const chunkIndex = res.metadata?.chunk_id ?? index;
                const sourceTitle = res.metadata?.title || '未知教材文档';
                const subject = res.metadata?.subject || '未分类';

                return (
                  <div
                    key={index}
                    className="p-4 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-2.5 hover:border-neutral-500 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(65,65,65,0.8)] pb-2">
                      <div className="flex items-center space-x-2 text-xs">
                        <FileText className="w-3.5 h-3.5 text-[#FAFF69]" />
                        <span className="text-white font-bold">{sourceTitle}</span>
                        <span className="text-neutral-500">|</span>
                        <span className="text-[#FAFF69]">{subject}</span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 border border-[#4ADE80] bg-[#4ADE80]/10 text-[#4ADE80] text-xs font-mono font-bold">
                          [SCORE: {formattedScore} | CHUNK #{chunkIndex}]
                        </span>
                      </div>
                    </div>

                    {/* Chunk Content */}
                    <div className="p-3 bg-black border border-[rgba(65,65,65,0.8)] text-neutral-200 text-xs whitespace-pre-wrap font-sans leading-relaxed">
                      {res.content}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
