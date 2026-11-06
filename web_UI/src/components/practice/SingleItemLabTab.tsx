import React, { useState } from 'react';
import {
  FlaskConical,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
  BookOpen,
  BookmarkPlus,
  Loader2,
} from 'lucide-react';
import { SingleItemGradeResponse, GradeStatus } from '@/types/practice';

interface SingleItemLabTabProps {
  initialQuestion?: string;
  initialStudentAnswer?: string;
  initialCorrectAnswer?: string;
}

export const SingleItemLabTab: React.FC<SingleItemLabTabProps> = ({
  initialQuestion = '',
  initialStudentAnswer = '',
  initialCorrectAnswer = '',
}) => {
  const [question, setQuestion] = useState(initialQuestion);
  const [studentAnswer, setStudentAnswer] = useState(initialStudentAnswer);
  const [correctAnswer, setCorrectAnswer] = useState(initialCorrectAnswer);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SingleItemGradeResponse | null>(null);
  const [isSavingMistake, setIsSavingMistake] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // 单题判分执行
  const handleGrade = async () => {
    if (!question.trim()) return;
    setIsLoading(true);
    setSaveSuccess(false);
    try {
      const res = await fetch('/v1/items/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          student: studentAnswer,
          correct: correctAnswer,
        }),
      });
      if (res.ok) {
        const data: SingleItemGradeResponse = await res.json();
        setResult(data);
      } else {
        const err = await res.text();
        alert(`单题判分失败 [${res.status}]: ${err}`);
      }
    } catch (e: any) {
      alert(`网络异常: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // 一键录入错题本 (POST /v1/mistakes)
  const handleSaveMistake = async () => {
    if (!result || isSavingMistake) return;
    setIsSavingMistake(true);
    try {
      const concept = result.diagnosed?.concept || '考点未指定';
      const errorType = result.diagnosed?.error_type || '理解错误';

      const res = await fetch('/v1/mistakes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'student',
          subject: '数学',
          concept,
          error_type: errorType,
          question_text: question,
          student_answer: studentAnswer,
          correct_answer: correctAnswer,
        }),
      });

      if (res.ok) {
        setSaveSuccess(true);
      } else {
        const err = await res.text();
        alert(`错题录入失败: ${err}`);
      }
    } catch (e: any) {
      alert(`保存异常: ${e.message}`);
    } finally {
      setIsSavingMistake(false);
    }
  };

  const status: GradeStatus = result?.graded.status || 'ungraded';

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-bg font-mono text-xs">
      {/* 头部标题与说明 */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-accent" />
          <span className="font-bold uppercase tracking-label text-text-primary text-xs">
            单题对照判分与错因变式实验室 (SINGLE_ITEM_LAB)
          </span>
        </div>
        <span className="text-[11px] text-text-muted">毫秒级离线比对 · 自动错因分类 · 3道同考点变式</span>
      </div>

      {/* 三栏硬质输入卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. 题干 */}
        <div className="border border-border bg-surface p-4 rounded-sm flex flex-col">
          <label className="text-[10px] text-text-muted uppercase font-bold mb-2 block">
            1. 原题题干 (QUESTION)
          </label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={5}
            placeholder="输入题目内容与选项，例如：已知集合 A={1, 2}，B={2, 3}，求 A∩B..."
            className="flex-1 bg-surface-2 border border-border p-3 text-xs text-text-primary focus:outline-none focus:border-accent resize-none leading-relaxed"
          />
        </div>

        {/* 2. 学生作答 */}
        <div className="border border-border bg-surface p-4 rounded-sm flex flex-col">
          <label className="text-[10px] text-text-muted uppercase font-bold mb-2 block">
            2. 学生作答 (STUDENT_ANSWER)
          </label>
          <textarea
            value={studentAnswer}
            onChange={(e) => setStudentAnswer(e.target.value)}
            rows={5}
            placeholder="输入学生的实际作答内容，例如：{1, 2, 3}"
            className="flex-1 bg-surface-2 border border-border p-3 text-xs text-text-primary focus:outline-none focus:border-accent resize-none leading-relaxed font-bold"
          />
        </div>

        {/* 3. 标准答案 */}
        <div className="border border-border bg-surface p-4 rounded-sm flex flex-col">
          <label className="text-[10px] text-text-muted uppercase font-bold mb-2 block">
            3. 标准答案 (CORRECT_ANSWER)
          </label>
          <textarea
            value={correctAnswer}
            onChange={(e) => setCorrectAnswer(e.target.value)}
            rows={5}
            placeholder="输入标准参考答案（若留空则无法判分），例如：{2}"
            className="flex-1 bg-surface-2 border border-border p-3 text-xs text-[#4ADE80] focus:outline-none focus:border-accent resize-none leading-relaxed font-bold"
          />
        </div>
      </div>

      {/* 判分操作条 */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <div className="text-[11px] text-text-muted">
          提示：没有标准答案时系统将返回 <span className="text-accent">[UNGRADED]</span> 并拒绝主观编造。
        </div>
        <button
          onClick={handleGrade}
          disabled={isLoading || !question.trim()}
          className="px-6 py-2.5 bg-accent active:bg-accent-active text-bg font-bold uppercase tracking-label rounded-xs flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4 fill-current" />}
          <span>EXECUTE_SINGLE_GRADE</span>
        </button>
      </div>

      {/* 诊断与判分结果呈现 */}
      {result && (
        <div className="border border-border bg-surface rounded-sm p-4 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div className="flex items-center gap-3">
              <span className="text-text-muted uppercase text-[10px]">判定结果:</span>
              {status === 'correct' ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 font-bold rounded-xs bg-[#4ADE80]/10 border border-[#4ADE80]/50 text-[#4ADE80]">
                  <CheckCircle2 className="w-4 h-4" /> [CORRECT / 正确]
                </span>
              ) : status === 'incorrect' ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 font-bold rounded-xs bg-[#F87171]/10 border border-[#F87171]/50 text-[#F87171]">
                  <AlertCircle className="w-4 h-4" /> [INCORRECT / 错误]
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 font-bold rounded-xs bg-surface-2 border border-dashed border-[#52525B] text-[#A1A1AA]">
                  <HelpCircle className="w-4 h-4" /> [UNGRADED / 未能判分 (缺标准答案)]
                </span>
              )}
            </div>

            {status === 'incorrect' && (
              <button
                onClick={handleSaveMistake}
                disabled={isSavingMistake || saveSuccess}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xs font-bold uppercase text-[11px] border transition-colors ${
                  saveSuccess
                    ? 'bg-[#4ADE80]/10 border-[#4ADE80] text-[#4ADE80]'
                    : 'bg-surface-2 border-accent text-accent hover:bg-accent hover:text-bg'
                }`}
              >
                {isSavingMistake ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <BookmarkPlus className="w-3.5 h-3.5" />
                )}
                <span>{saveSuccess ? '已入库错题本' : '入库至错题本'}</span>
              </button>
            )}
          </div>

          {/* 深度错因归因卡片 */}
          {result.diagnosed && (
            <div className="p-3 bg-surface-2 border border-border rounded-xs space-y-1.5">
              <div className="text-[10px] text-accent uppercase font-bold flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>智能错因归因 (ERROR_DIAGNOSIS)</span>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-1">
                <div>
                  <span className="text-text-muted">核心考点: </span>
                  <span className="text-text-primary font-bold">{result.diagnosed.concept}</span>
                </div>
                <div>
                  <span className="text-text-muted">错因类别: </span>
                  <span className="text-[#F87171] font-bold">{result.diagnosed.error_type}</span>
                </div>
              </div>
              {result.diagnosed.explanation && (
                <p className="text-[11px] text-text-muted mt-2 pt-2 border-t border-border/40 leading-relaxed">
                  {result.diagnosed.explanation}
                </p>
              )}
            </div>
          )}

          {/* 3 道同考点文字变式题 */}
          {result.variants && result.variants.length > 0 && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center gap-2 text-text-primary text-xs font-bold uppercase">
                <BookOpen className="w-4 h-4 text-accent" />
                <span>同考点推荐变式训练 (3 VARIANTS)</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {result.variants.map((varText, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-surface-2 border border-border/80 rounded-xs flex flex-col justify-between"
                  >
                    <div>
                      <div className="text-[10px] text-accent font-bold uppercase mb-1.5">
                        变式试题 #{idx + 1}
                      </div>
                      <p className="text-[11px] text-text-secondary leading-relaxed">{varText}</p>
                    </div>
                    <button
                      onClick={() => {
                        setQuestion(varText);
                        setStudentAnswer('');
                        setCorrectAnswer('');
                        setResult(null);
                      }}
                      className="mt-3 text-[10px] text-text-muted hover:text-accent flex items-center justify-end gap-1 pt-2 border-t border-border/40"
                    >
                      <span>载入本题练习 -&gt;</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
