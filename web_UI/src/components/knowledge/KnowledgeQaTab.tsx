import React, { useState, useEffect } from 'react';
import { askKnowledge } from '@/lib/api-client';
import { KnowledgeAskResponse } from '@/types/knowledge';
import {
  MessageSquare,
  RotateCcw,
  Sparkles,
  BookOpen,
  ArrowRight,
  AlertTriangle,
  SlidersHorizontal,
  CheckCircle2,
} from 'lucide-react';

interface KnowledgeQaTabProps {
  totalDocuments: number;
  initialQuery?: string;
  onSwitchToManager?: () => void;
}

export const KnowledgeQaTab: React.FC<KnowledgeQaTabProps> = ({
  totalDocuments,
  initialQuery,
  onSwitchToManager,
}) => {
  const [question, setQuestion] = useState(initialQuery || '');
  const [topK, setTopK] = useState(3);
  const [subjectFilter, setSubjectFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<KnowledgeAskResponse | null>(null);

  useEffect(() => {
    if (initialQuery) {
      setQuestion(initialQuery);
    }
  }, [initialQuery]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    try {
      const res = await askKnowledge(
        question.trim(),
        topK,
        subjectFilter.trim() || undefined
      );
      setResponse(res);
    } catch (err: any) {
      alert(`问答生成失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Empty Index Guard */}
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
            知识库内尚无文档，大模型将只能依赖基模型自身知识，无法挂载本地教材切片。
          </p>
        </div>
      )}

      {/* Query Formulation Form */}
      <form
        onSubmit={handleAsk}
        className="p-5 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-4"
      >
        <div className="flex items-center justify-between border-b border-[rgba(65,65,65,0.8)] pb-2">
          <span className="text-xs text-[#FAFF69] font-bold flex items-center space-x-1.5">
            <MessageSquare className="w-4 h-4" />
            <span>[RAG_SYNTHESIS_WORKBENCH / 知识库增强问答]</span>
          </span>
          <span className="text-[10px] text-neutral-500">
            向量检索关联切片作为上下文，送入大语言模型进行精准推导
          </span>
        </div>

        <div>
          <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
            QUESTION_PROMPT / 向知识库提问:
          </label>
          <textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="例如：请结合高等数学教材，解释罗尔中值定理与拉格朗日中值定理的关系..."
            className="w-full bg-black border border-[rgba(65,65,65,0.8)] p-3 text-xs text-white focus:outline-none focus:border-[#FAFF69] font-sans"
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold flex items-center space-x-1">
              <SlidersHorizontal className="w-3 h-3" />
              <span>RAG_CONTEXT_CHUNKS / 检索参考切片数 (Top-K):</span>
            </label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            >
              <option value={1}>1 个切片 (精准上下文)</option>
              <option value={3}>3 个切片 (推荐平衡)</option>
              <option value={5}>5 个切片 (丰富上下文)</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              SUBJECT_CONSTRAINT / 限定学科 (可选):
            </label>
            <input
              type="text"
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
              placeholder="例如：高等数学"
              className="w-full bg-black border border-[rgba(65,65,65,0.8)] px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
            />
          </div>
        </div>

        <div className="flex items-center justify-end pt-2 border-t border-[rgba(65,65,65,0.8)]">
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="px-6 py-2.5 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 disabled:opacity-50 flex items-center space-x-1.5 cursor-pointer"
          >
            {loading ? (
              <>
                <RotateCcw className="w-4 h-4 animate-spin" />
                <span>SYNTHESIZING_RAG_ANSWER...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>ASK_KNOWLEDGE_BASE</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Answer Presentation Card */}
      {response && (
        <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] divide-y divide-[rgba(65,65,65,0.8)]">
          {/* Header Bar */}
          <div className="p-3 bg-black flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2 text-[#4ADE80] font-bold">
              <CheckCircle2 className="w-4 h-4 text-[#4ADE80]" />
              <span>RAG_SYNTHESIZED_RESPONSE</span>
            </div>
            {response.trace_id && (
              <span className="text-[10px] text-neutral-500 font-mono">
                [AUDIT_TRACE: {response.trace_id}]
              </span>
            )}
          </div>

          {/* Answer Body */}
          <div className="p-5 text-sm text-neutral-100 whitespace-pre-wrap font-sans leading-relaxed">
            {response.answer}
          </div>

          {/* Source Document Citations */}
          {response.sources && response.sources.length > 0 && (
            <div className="p-4 bg-black/60 space-y-2">
              <div className="text-[10px] text-neutral-400 font-bold uppercase tracking-wider flex items-center space-x-1">
                <BookOpen className="w-3.5 h-3.5 text-[#FAFF69]" />
                <span>CITED_KNOWLEDGE_SOURCES / 参考引用课件:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {response.sources.map((src, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-xs text-neutral-300 font-mono flex items-center space-x-1"
                  >
                    <span className="text-[#FAFF69]">[{i + 1}]</span>
                    <span>{src}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
