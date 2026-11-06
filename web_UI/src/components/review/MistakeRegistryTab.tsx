import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchMistakes,
  confirmMistake,
  dismissMistake,
  createMistake,
} from '@/lib/api-client';
import { MistakeItem, MistakeStatus, CreateMistakePayload } from '@/types/review';
import {
  Plus,
  CheckCircle2,
  XCircle,
  Play,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Filter,
  CheckCheck,
} from 'lucide-react';

interface MistakeRegistryTabProps {
  onPracticeMistake?: (mistakeId: string) => void;
}

export const MistakeRegistryTab: React.FC<MistakeRegistryTabProps> = ({
  onPracticeMistake,
}) => {
  const [mistakes, setMistakes] = useState<MistakeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [bulkConfirming, setBulkConfirming] = useState(false);

  // Manual entry form state
  const [formSubject, setFormSubject] = useState('高等数学');
  const [formConcept, setFormConcept] = useState('');
  const [formErrorType, setFormErrorType] = useState('概念混淆');
  const [formQuestion, setFormQuestion] = useState('');
  const [formStudentAnswer, setFormStudentAnswer] = useState('');
  const [formCorrectAnswer, setFormCorrectAnswer] = useState('');
  const [formAnalysis, setFormAnalysis] = useState('');
  const [formSubmitting, setFormSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchMistakes(statusFilter === 'all' ? undefined : statusFilter, 'student');
      setMistakes(data);
    } catch (err: any) {
      console.error('Failed to load mistakes', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleConfirm = async (id: string) => {
    setActionLoadingId(id);
    try {
      await confirmMistake(id);
      await loadData();
    } catch (err: any) {
      alert(`确认失败: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDismiss = async (id: string) => {
    setActionLoadingId(id);
    try {
      await dismissMistake(id);
      await loadData();
    } catch (err: any) {
      alert(`丢弃失败: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleConfirmAllPending = async () => {
    const pendingItems = mistakes.filter((m) => m.status === 'pending');
    if (pendingItems.length === 0) return;

    setBulkConfirming(true);
    try {
      await Promise.all(pendingItems.map((m) => confirmMistake(m.id)));
      await loadData();
    } catch (err: any) {
      alert(`批量确认失败: ${err.message}`);
    } finally {
      setBulkConfirming(false);
    }
  };

  const handleCreateMistake = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formQuestion.trim() || !formConcept.trim()) {
      alert('题干与考点为必填项');
      return;
    }

    setFormSubmitting(true);
    try {
      const payload: CreateMistakePayload = {
        user_id: 'student',
        subject: formSubject,
        concept: formConcept.trim(),
        error_type: formErrorType,
        question_text: formQuestion.trim(),
        student_answer: formStudentAnswer.trim(),
        correct_answer: formCorrectAnswer.trim(),
        analysis: formAnalysis.trim(),
      };
      await createMistake(payload);
      // Reset form
      setFormConcept('');
      setFormQuestion('');
      setFormStudentAnswer('');
      setFormCorrectAnswer('');
      setFormAnalysis('');
      setShowManualForm(false);
      // Reload pending
      setStatusFilter('pending');
      await loadData();
    } catch (err: any) {
      alert(`创建错题失败: ${err.message}`);
    } finally {
      setFormSubmitting(false);
    }
  };

  const getStatusBadge = (status: MistakeStatus) => {
    switch (status) {
      case 'pending':
        return (
          <span className="px-1.5 py-0.5 border border-[#FAFF69] bg-[#FAFF69]/10 text-[#FAFF69] text-[10px] font-bold">
            [PENDING]
          </span>
        );
      case 'confirmed':
        return (
          <span className="px-1.5 py-0.5 border border-[#4ADE80] bg-[#4ADE80]/10 text-[#4ADE80] text-[10px] font-bold">
            [CONFIRMED]
          </span>
        );
      case 'dismissed':
        return (
          <span className="px-1.5 py-0.5 border border-neutral-600 bg-neutral-800 text-neutral-400 text-[10px]">
            [DISMISSED]
          </span>
        );
      default:
        return null;
    }
  };

  const pendingCountInView = mistakes.filter((m) => m.status === 'pending').length;

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Top Filter and Actions Bar */}
      <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] flex flex-wrap items-center justify-between gap-3">
        {/* Status Filters */}
        <div className="flex items-center space-x-1">
          <Filter className="w-3.5 h-3.5 text-neutral-500 mr-1" />
          {(['pending', 'confirmed', 'dismissed', 'all'] as const).map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 text-xs uppercase tracking-wider transition-colors ${
                statusFilter === st
                  ? 'bg-[#FAFF69] text-black font-bold'
                  : 'text-neutral-400 hover:text-white border border-[rgba(65,65,65,0.8)]'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          {statusFilter === 'pending' && pendingCountInView > 0 && (
            <button
              type="button"
              disabled={bulkConfirming}
              onClick={handleConfirmAllPending}
              className="px-3 py-1 bg-[#4ADE80] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 flex items-center space-x-1 disabled:opacity-50"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              <span>CONFIRM_ALL_PENDING ({pendingCountInView})</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowManualForm((prev) => !prev)}
            className={`px-3 py-1 text-xs uppercase tracking-wider flex items-center space-x-1 border transition-colors ${
              showManualForm
                ? 'bg-neutral-800 border-neutral-600 text-white'
                : 'border-[rgba(65,65,65,0.8)] text-[#FAFF69] hover:bg-[#FAFF69]/10'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{showManualForm ? 'CLOSE_FORM' : '+ MANUAL_ENTRY'}</span>
          </button>

          <button
            type="button"
            onClick={loadData}
            className="p-1 border border-[rgba(65,65,65,0.8)] text-neutral-400 hover:text-white"
            title="Refresh"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Manual Entry Collapsible Form */}
      {showManualForm && (
        <form
          onSubmit={handleCreateMistake}
          className="p-5 border border-[#FAFF69] bg-black space-y-4 animate-in fade-in duration-150"
        >
          <div className="flex items-center justify-between border-b border-[rgba(65,65,65,0.8)] pb-2">
            <span className="text-xs text-[#FAFF69] font-bold">
              [MANUAL_MISTAKE_INGESTION_FORM / 手工录入错题]
            </span>
            <span className="text-[10px] text-neutral-500">
              录入后初始状态为 pending，将进入错题库审核流
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
                SUBJECT / 学科:
              </label>
              <input
                type="text"
                value={formSubject}
                onChange={(e) => setFormSubject(e.target.value)}
                className="w-full bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] px-2.5 py-1 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
                placeholder="例如：高等数学 / 概率论"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
                CONCEPT / 考点*:
              </label>
              <input
                type="text"
                value={formConcept}
                onChange={(e) => setFormConcept(e.target.value)}
                className="w-full bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] px-2.5 py-1 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
                placeholder="例如：泰勒展开极值判定"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
                ERROR_TYPE / 错因类型:
              </label>
              <select
                value={formErrorType}
                onChange={(e) => setFormErrorType(e.target.value)}
                className="w-full bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] px-2 py-1 text-xs text-white focus:outline-none focus:border-[#FAFF69]"
              >
                <option value="概念混淆">概念混淆 (CONCEPT_CONFUSION)</option>
                <option value="计算失误">计算失误 (CALCULATION_ERROR)</option>
                <option value="题意误解">题意误解 (MISREAD_PROMPT)</option>
                <option value="方法不当">方法不当 (SUBOPTIMAL_METHOD)</option>
                <option value="记忆遗忘">记忆遗忘 (FORGOTTEN_FORMULA)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              QUESTION_TEXT / 题干*:
            </label>
            <textarea
              rows={3}
              value={formQuestion}
              onChange={(e) => setFormQuestion(e.target.value)}
              className="w-full bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] p-2 text-xs text-white focus:outline-none focus:border-[#FAFF69] font-sans"
              placeholder="输入完整题目内容..."
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-red-400 mb-1 font-bold">
                STUDENT_ANSWER / 错误作答:
              </label>
              <textarea
                rows={2}
                value={formStudentAnswer}
                onChange={(e) => setFormStudentAnswer(e.target.value)}
                className="w-full bg-[#0A0A0A] border border-red-900/60 p-2 text-xs text-red-200 focus:outline-none focus:border-red-500 font-sans"
                placeholder="当时写错的答案或推导过程..."
              />
            </div>
            <div>
              <label className="block text-[10px] text-[#4ADE80] mb-1 font-bold">
                CORRECT_ANSWER / 标准答案:
              </label>
              <textarea
                rows={2}
                value={formCorrectAnswer}
                onChange={(e) => setFormCorrectAnswer(e.target.value)}
                className="w-full bg-[#0A0A0A] border border-[#4ADE80]/50 p-2 text-xs text-[#4ADE80] focus:outline-none focus:border-[#4ADE80] font-sans"
                placeholder="标准正确答案..."
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-neutral-400 mb-1 font-bold">
              ANALYSIS / 根因解析与防坑指引:
            </label>
            <textarea
              rows={2}
              value={formAnalysis}
              onChange={(e) => setFormAnalysis(e.target.value)}
              className="w-full bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] p-2 text-xs text-neutral-300 focus:outline-none focus:border-[#FAFF69] font-sans"
              placeholder="解析及防坑指南..."
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setShowManualForm(false)}
              className="px-3 py-1.5 border border-[rgba(65,65,65,0.8)] text-neutral-400 hover:text-white text-xs"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={formSubmitting}
              className="px-4 py-1.5 bg-[#FAFF69] text-black text-xs font-bold hover:brightness-110 disabled:opacity-50 uppercase"
            >
              {formSubmitting ? 'INGESTING...' : 'SAVE_TO_REGISTRY'}
            </button>
          </div>
        </form>
      )}

      {/* Mistake Registry Table */}
      {loading ? (
        <div className="p-12 text-center border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-500">
          [FETCHING_MISTAKES_FROM_SQLITE...]
        </div>
      ) : mistakes.length === 0 ? (
        <div className="p-12 text-center border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-500 space-y-2">
          <div>NO_MISTAKES_FOUND_FOR_FILTER: [{statusFilter.toUpperCase()}]</div>
          <p className="text-xs text-neutral-600">
            暂无此分类下的错题记录，可在练习工作台批改试卷或通过上方「+ MANUAL_ENTRY」录入。
          </p>
        </div>
      ) : (
        <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] divide-y divide-[rgba(65,65,65,0.8)]">
          {mistakes.map((m) => {
            const isExpanded = expandedId === m.id;
            const isActing = actionLoadingId === m.id;

            return (
              <div key={m.id} className="hover:bg-white/[0.02] transition-colors">
                {/* Row Header */}
                <div className="p-3 flex items-center justify-between gap-3">
                  <div
                    className="flex items-center space-x-3 cursor-pointer flex-1 min-w-0"
                    onClick={() => setExpandedId(isExpanded ? null : m.id)}
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-[#FAFF69] flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-neutral-500 flex-shrink-0" />
                    )}

                    <span className="text-xs text-neutral-400 font-mono flex-shrink-0">
                      [{m.id}]
                    </span>

                    {getStatusBadge(m.status)}

                    <span className="text-xs text-white font-bold truncate">
                      {m.subject || 'GENERAL'} / {m.concept}
                    </span>

                    <span className="text-[10px] text-neutral-500 hidden md:inline truncate">
                      {m.question_text.slice(0, 45)}...
                    </span>
                  </div>

                  {/* Quick Row Actions */}
                  <div className="flex items-center space-x-2 flex-shrink-0">
                    {m.status === 'pending' && (
                      <>
                        <button
                          type="button"
                          disabled={isActing}
                          onClick={() => handleConfirm(m.id)}
                          className="px-2 py-0.5 border border-[#4ADE80] text-[#4ADE80] hover:bg-[#4ADE80] hover:text-black text-[10px] font-bold flex items-center space-x-1"
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          <span>CONFIRM</span>
                        </button>
                        <button
                          type="button"
                          disabled={isActing}
                          onClick={() => handleDismiss(m.id)}
                          className="px-2 py-0.5 border border-red-500/60 text-red-400 hover:bg-red-500 hover:text-white text-[10px] flex items-center space-x-1"
                        >
                          <XCircle className="w-3 h-3" />
                          <span>DISMISS</span>
                        </button>
                      </>
                    )}

                    {m.status === 'confirmed' && (
                      <>
                        <button
                          type="button"
                          onClick={() => onPracticeMistake?.(m.id)}
                          className="px-2 py-0.5 bg-[#FAFF69] text-black text-[10px] font-bold flex items-center space-x-1 hover:brightness-110"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          <span>PRACTICE_NOW</span>
                        </button>
                        <button
                          type="button"
                          disabled={isActing}
                          onClick={() => handleDismiss(m.id)}
                          className="px-2 py-0.5 border border-neutral-700 text-neutral-500 hover:text-red-400 text-[10px]"
                        >
                          DISMISS
                        </button>
                      </>
                    )}

                    {m.status === 'dismissed' && (
                      <button
                        type="button"
                        disabled={isActing}
                        onClick={() => handleConfirm(m.id)}
                        className="px-2 py-0.5 border border-neutral-600 text-neutral-400 hover:text-white text-[10px]"
                      >
                        RE-CONFIRM
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded Detail Accordion */}
                {isExpanded && (
                  <div className="px-5 py-4 bg-black border-t border-[rgba(65,65,65,0.8)] space-y-3 text-xs">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px] text-neutral-400 pb-2 border-b border-neutral-800">
                      <div>REPETITIONS: {m.repetitions}</div>
                      <div>INTERVAL: {m.interval_days} DAYS</div>
                      <div>EASE: {Number(m.ease || 2.5).toFixed(2)}</div>
                      <div>NEXT_REVIEW: {m.next_review_at || 'NOT_SCHEDULED'}</div>
                    </div>

                    <div>
                      <div className="text-[10px] text-neutral-500 font-bold mb-1">
                        FULL_QUESTION_TEXT:
                      </div>
                      <div className="p-3 bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] text-neutral-200 whitespace-pre-wrap font-sans">
                        {m.question_text}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <div className="text-[10px] text-red-400 font-bold mb-1">
                          STUDENT_ANSWER:
                        </div>
                        <div className="p-2.5 bg-red-950/20 border border-red-900/50 text-red-300 whitespace-pre-wrap font-sans">
                          {m.student_answer || '（未记录）'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-[#4ADE80] font-bold mb-1">
                          CORRECT_ANSWER:
                        </div>
                        <div className="p-2.5 bg-[#4ADE80]/5 border border-[#4ADE80]/30 text-[#4ADE80] whitespace-pre-wrap font-mono">
                          {m.correct_answer || '（未记录）'}
                        </div>
                      </div>
                    </div>

                    {m.analysis && (
                      <div>
                        <div className="text-[10px] text-neutral-400 font-bold mb-1">
                          ROOT_CAUSE_DIAGNOSIS:
                        </div>
                        <div className="p-2.5 bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] text-neutral-300 whitespace-pre-wrap font-sans leading-relaxed">
                          {m.analysis}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
