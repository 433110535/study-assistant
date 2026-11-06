import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchDueReviews,
  fetchMistakes,
  reviewMistake,
  rescheduleMistake,
} from '@/lib/api-client';
import { MistakeItem, ReviewResponse } from '@/types/review';
import {
  RotateCcw,
  Sparkles,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Flame,
} from 'lucide-react';

interface DueReviewDeckTabProps {
  onSwitchTab?: (tab: 'deck' | 'registry' | 'mastery') => void;
  targetMistakeId?: string | null;
  onClearTargetMistake?: () => void;
}

export const DueReviewDeckTab: React.FC<DueReviewDeckTabProps> = ({
  onSwitchTab,
  targetMistakeId,
  onClearTargetMistake,
}) => {
  const [deck, setDeck] = useState<MistakeItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [confirmedCount, setConfirmedCount] = useState(0);
  const [telemetryMessage, setTelemetryMessage] = useState<string | null>(null);
  const [deckMode, setDeckMode] = useState<'due' | 'forced'>('due');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Fetch due mistakes
      const dueItems = await fetchDueReviews('student');
      // 2. Fetch pending and confirmed counts
      const [pendingItems, confirmedItems] = await Promise.all([
        fetchMistakes('pending', 'student'),
        fetchMistakes('confirmed', 'student'),
      ]);

      setPendingCount(pendingItems.length);
      setConfirmedCount(confirmedItems.length);

      if (targetMistakeId) {
        // If targeted specific mistake (e.g. from registry "Practice Now")
        const targeted = confirmedItems.find((m) => m.id === targetMistakeId);
        if (targeted) {
          setDeck([targeted]);
          setCurrentIndex(0);
          setIsFlipped(false);
          setDeckMode('forced');
          setLoading(false);
          return;
        }
      }

      setDeck(dueItems);
      setCurrentIndex(0);
      setIsFlipped(false);
      setDeckMode('due');
    } catch (err: any) {
      console.error('Failed to load review items', err);
    } finally {
      setLoading(false);
    }
  }, [targetMistakeId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleForceReviewConfirmed = async () => {
    setLoading(true);
    try {
      const confirmedItems = await fetchMistakes('confirmed', 'student');
      setDeck(confirmedItems);
      setCurrentIndex(0);
      setIsFlipped(false);
      setDeckMode('forced');
    } catch (err: any) {
      console.error('Failed to force load confirmed mistakes', err);
    } finally {
      setLoading(false);
    }
  };

  const currentCard = deck[currentIndex];

  const handleRating = useCallback(async (quality: number) => {
    if (!currentCard || submitting) return;
    setSubmitting(true);
    try {
      const res: ReviewResponse = await reviewMistake(currentCard.id, quality);
      // Flash telemetry banner
      const msg = `LAST_SYNC: [${res.id}] -> EASE: ${Number(res.ease).toFixed(2)} | INTERVAL: +${res.interval_days}D | REPS: ${res.repetitions}`;
      setTelemetryMessage(msg);
      setTimeout(() => setTelemetryMessage(null), 3000);

      if (currentIndex + 1 < deck.length) {
        setCurrentIndex((prev) => prev + 1);
        setIsFlipped(false);
      } else {
        // Completed deck
        setCurrentIndex(deck.length);
        if (onClearTargetMistake) onClearTargetMistake();
      }
    } catch (err: any) {
      alert(`复习同步失败: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }, [currentCard, submitting, currentIndex, deck.length, onClearTargetMistake]);

  const handleRescheduleEvening = async () => {
    if (!currentCard || submitting) return;
    setSubmitting(true);
    try {
      await rescheduleMistake(currentCard.id, '推到晚上');
      const msg = `RESCHEDULED: [${currentCard.id}] -> MOVED_TO_EVENING (TONIGHT)`;
      setTelemetryMessage(msg);
      setTimeout(() => setTelemetryMessage(null), 3000);

      if (currentIndex + 1 < deck.length) {
        setCurrentIndex((prev) => prev + 1);
        setIsFlipped(false);
      } else {
        setCurrentIndex(deck.length);
        if (onClearTargetMistake) onClearTargetMistake();
      }
    } catch (err: any) {
      alert(`改期失败: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }
      if (!currentCard || currentIndex >= deck.length) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (isFlipped && !submitting) {
        if (e.key === '1') {
          e.preventDefault();
          handleRating(1);
        } else if (e.key === '2') {
          e.preventDefault();
          handleRating(3);
        } else if (e.key === '3') {
          e.preventDefault();
          handleRating(4);
        } else if (e.key === '4') {
          e.preventDefault();
          handleRating(5);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentCard, isFlipped, submitting, currentIndex, deck.length, handleRating]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
        <RotateCcw className="w-8 h-8 text-[#FAFF69] animate-spin" />
        <div className="font-mono text-xs tracking-wider text-neutral-400">
          [QUERYING_SM2_DUE_QUEUE_STATE...]
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Telemetry Flash Banner */}
      {telemetryMessage && (
        <div className="px-4 py-2 bg-[#FAFF69]/10 border border-[#FAFF69] text-[#FAFF69] text-xs font-mono flex items-center justify-between animate-in fade-in duration-200">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-[#FAFF69]" />
            <span>{telemetryMessage}</span>
          </div>
          <span className="text-[10px] text-neutral-400">[TELEMETRY_RECORDED]</span>
        </div>
      )}

      {/* When Due Deck is Empty */}
      {deck.length === 0 || currentIndex >= deck.length ? (
        <div className="p-8 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 border border-[#FAFF69] text-[#FAFF69] bg-black">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-wide">
                {deck.length > 0 && currentIndex >= deck.length
                  ? 'REVIEW_SESSION_COMPLETE'
                  : 'NO_DUE_REVIEWS_FOR_TODAY'}
              </h3>
              <p className="text-xs text-neutral-400 mt-1">
                {deck.length > 0 && currentIndex >= deck.length
                  ? `已完成本轮 ${deck.length} 道错题的记忆强化与 SM-2 周期重排。`
                  : '当前没有到期的 SM-2 复习任务。'}
              </p>
            </div>
          </div>

          {/* Pending Mistakes Alert Banner */}
          {pendingCount > 0 && (
            <div className="p-4 border border-[#FAFF69] bg-[#FAFF69]/5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-[#FAFF69] text-xs font-bold">
                  <AlertCircle className="w-4 h-4" />
                  <span>DETECTED [{pendingCount}] PENDING MISTAKES AWAITING CONFIRMATION</span>
                </div>
                <button
                  type="button"
                  onClick={() => onSwitchTab?.('registry')}
                  className="px-3 py-1 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 flex items-center space-x-1"
                >
                  <span>GO_TO_MISTAKE_REGISTRY</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-xs text-neutral-400">
                试卷批改或练习中自动捕获的错题默认处于 pending 待确认状态，需确认入库后才进入 SM-2 调度轮次。
              </p>
            </div>
          )}

          {/* Force Review Confirmed Mistakes Action */}
          <div className="p-4 border border-[rgba(65,65,65,0.8)] bg-black space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-white font-bold flex items-center space-x-2">
                  <Flame className="w-4 h-4 text-[#FAFF69]" />
                  <span>EARLY_RECALL_CHALLENGE / 强化刷题模式</span>
                </div>
                <p className="text-xs text-neutral-400 mt-1">
                  已有 {confirmedCount} 道已确认入库错题。无须等到明日即可随时启动全量抽认卡提前打分复习。
                </p>
              </div>
              {confirmedCount > 0 && (
                <button
                  type="button"
                  onClick={handleForceReviewConfirmed}
                  className="px-4 py-2 border border-[#FAFF69] text-[#FAFF69] hover:bg-[#FAFF69] hover:text-black transition-colors text-xs font-bold uppercase tracking-wider"
                >
                  FORCE_REVIEW_CONFIRMED_DECK ({confirmedCount})
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-3 pt-2">
            <button
              type="button"
              onClick={loadData}
              className="px-4 py-2 border border-[rgba(65,65,65,0.8)] text-neutral-300 hover:text-white hover:border-neutral-400 text-xs tracking-wider flex items-center space-x-2"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>RELOAD_DECK</span>
            </button>
            <button
              type="button"
              onClick={() => onSwitchTab?.('mastery')}
              className="px-4 py-2 border border-[rgba(65,65,65,0.8)] text-neutral-300 hover:text-white hover:border-neutral-400 text-xs tracking-wider flex items-center space-x-2"
            >
              <span>CHECK_MASTERY_RADAR</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ) : (
        /* Active Flashcard Review Card */
        <div className="space-y-4">
          {/* Deck Header & Progress */}
          <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="px-2 py-0.5 bg-black border border-[#FAFF69] text-[#FAFF69] text-xs font-bold">
                {deckMode === 'forced' ? 'EARLY_REVIEW' : 'DUE_TODAY'}
              </span>
              <span className="text-xs text-neutral-400">
                CARD {currentIndex + 1} / {deck.length}
              </span>
              <span className="text-xs text-neutral-500">|</span>
              <span className="text-xs text-neutral-300">
                [ID: {currentCard.id}]
              </span>
            </div>
            <div className="flex items-center space-x-3 text-xs text-neutral-400">
              <span>REPETITIONS: {currentCard.repetitions}</span>
              <span>INTERVAL: {currentCard.interval_days}D</span>
              <span>EASE: {Number(currentCard.ease || 2.5).toFixed(2)}</span>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full h-1 bg-black border border-[rgba(65,65,65,0.8)]">
            <div
              className="h-full bg-[#FAFF69] transition-all duration-300"
              style={{
                width: `${((currentIndex + 1) / deck.length) * 100}%`,
              }}
            />
          </div>

          {/* Card Body */}
          <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] divide-y divide-[rgba(65,65,65,0.8)]">
            {/* Meta Tags Bar */}
            <div className="px-4 py-2 bg-black flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-neutral-500">[SUBJECT]:</span>
                <span className="text-white font-bold">{currentCard.subject || 'GENERAL'}</span>
                <span className="text-neutral-500 ml-2">[CONCEPT]:</span>
                <span className="text-[#FAFF69]">{currentCard.concept}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="px-1.5 py-0.5 border border-red-500/50 text-red-400 text-[10px]">
                  {currentCard.error_type || 'WRONG_LOGIC'}
                </span>
              </div>
            </div>

            {/* Question Text */}
            <div className="p-5 space-y-2 bg-[#0A0A0A]">
              <div className="text-[10px] text-neutral-500 tracking-wider font-bold">
                QUESTION_PROMPT / 题干:
              </div>
              <div className="text-sm text-neutral-100 whitespace-pre-wrap leading-relaxed font-sans font-medium">
                {currentCard.question_text}
              </div>
            </div>

            {/* Student's Historical Mistake Answer */}
            <div className="p-5 space-y-2 bg-black/60">
              <div className="text-[10px] text-red-400 tracking-wider font-bold flex items-center space-x-1">
                <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                <span>YOUR_PREVIOUS_WRONG_ANSWER / 历史作答:</span>
              </div>
              <div className="p-3 border border-red-900/50 bg-red-950/20 text-red-300 text-xs whitespace-pre-wrap font-sans">
                {currentCard.student_answer || '（未记录作答内容）'}
              </div>
            </div>

            {/* Flipped Content: Standard Answer & Diagnostic Analysis */}
            {isFlipped ? (
              <div className="p-5 space-y-4 bg-black border-t-2 border-[#FAFF69]/50 animate-in fade-in duration-200">
                {/* Standard Answer */}
                <div className="space-y-1.5">
                  <div className="text-[10px] text-[#4ADE80] tracking-wider font-bold flex items-center space-x-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#4ADE80]" />
                    <span>STANDARD_CORRECT_ANSWER / 标准答案:</span>
                  </div>
                  <div className="p-3 border border-[#4ADE80]/40 bg-[#4ADE80]/5 text-[#4ADE80] text-xs font-mono font-bold whitespace-pre-wrap">
                    {currentCard.correct_answer || '（无标准答案记录）'}
                  </div>
                </div>

                {/* Diagnostic Analysis */}
                {currentCard.analysis && (
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[10px] text-neutral-400 tracking-wider font-bold flex items-center space-x-1">
                      <HelpCircle className="w-3.5 h-3.5 text-neutral-400" />
                      <span>DIAGNOSTIC_ANALYSIS / 根因解析:</span>
                    </div>
                    <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-300 text-xs whitespace-pre-wrap font-sans leading-relaxed">
                      {currentCard.analysis}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Reveal Trigger Button */
              <div className="p-6 bg-black flex flex-col items-center justify-center space-y-2">
                <button
                  type="button"
                  onClick={() => setIsFlipped(true)}
                  className="px-6 py-3 bg-[#FAFF69] text-black text-xs font-bold tracking-wider hover:brightness-110 flex items-center space-x-2 uppercase cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>REVEAL_ANSWER_AND_DIAGNOSIS [SPACE]</span>
                </button>
                <span className="text-[10px] text-neutral-500">
                  按空格键或点击上方按钮翻转卡片，检验记忆回忆结果
                </span>
              </div>
            )}
          </div>

          {/* Control Bar: Quality Grading & Reschedule */}
          {isFlipped && (
            <div className="p-4 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] space-y-3 animate-in fade-in duration-200">
              <div className="text-xs text-neutral-400 font-bold flex items-center justify-between">
                <span>SM-2 QUALITY RATING / 回忆打分:</span>
                <span className="text-[10px] text-neutral-500">
                  支持快捷键 1 / 2 / 3 / 4 快速打分
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {/* 1: FORGOTTEN (quality: 1) */}
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRating(1)}
                  className="p-3 border border-[#F87171] text-[#F87171] hover:bg-[#F87171]/10 transition-colors flex flex-col items-center justify-center space-y-1 cursor-pointer disabled:opacity-50"
                >
                  <span className="text-xs font-bold">[1] FORGOTTEN / 完全重来</span>
                  <span className="text-[10px] text-neutral-500">间隔重设为 1 天</span>
                </button>

                {/* 2: HARD (quality: 3) */}
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRating(3)}
                  className="p-3 border border-[#FBBF24] text-[#FBBF24] hover:bg-[#FBBF24]/10 transition-colors flex flex-col items-center justify-center space-y-1 cursor-pointer disabled:opacity-50"
                >
                  <span className="text-xs font-bold">[2] HARD / 较困难回忆</span>
                  <span className="text-[10px] text-neutral-500">适度延长间隔</span>
                </button>

                {/* 3: GOOD (quality: 4) */}
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRating(4)}
                  className="p-3 border border-[#4ADE80] text-[#4ADE80] hover:bg-[#4ADE80]/10 transition-colors flex flex-col items-center justify-center space-y-1 cursor-pointer disabled:opacity-50"
                >
                  <span className="text-xs font-bold">[3] GOOD / 顺利回忆</span>
                  <span className="text-[10px] text-neutral-500">标准 SM-2 倍增</span>
                </button>

                {/* 4: EASY (quality: 5) */}
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleRating(5)}
                  className="p-3 bg-[#FAFF69] text-black hover:brightness-110 font-bold transition-transform flex flex-col items-center justify-center space-y-1 cursor-pointer disabled:opacity-50"
                >
                  <span className="text-xs font-bold">[4] EASY / 轻松掌握</span>
                  <span className="text-[10px] text-neutral-800">提升难易度因子 (Ease)</span>
                </button>
              </div>

              {/* Reschedule Option */}
              <div className="pt-2 border-t border-[rgba(65,65,65,0.8)] flex items-center justify-between text-xs">
                <span className="text-neutral-500 text-[10px]">
                  若今日暂时无暇深入推导本题：
                </span>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={handleRescheduleEvening}
                  className="px-3 py-1.5 border border-[rgba(65,65,65,0.8)] text-neutral-300 hover:text-white hover:border-neutral-400 flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Clock className="w-3.5 h-3.5 text-neutral-400" />
                  <span>RESCHEDULE_TO_EVENING (推到今晚)</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
