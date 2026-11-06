import React, { useState } from 'react';
import {
  Wand2,
  Eye,
  EyeOff,
  Send,
  Loader2,
  FileCheck,
} from 'lucide-react';
import { QuestionGenParams, QuizGradeResponse } from '@/types/practice';

export const QuestionGeneratorTab: React.FC = () => {
  const [topic, setTopic] = useState('高中数学 导数极值与单调性');
  const [difficulty, setDifficulty] = useState<QuestionGenParams['difficulty']>('中等');
  const [count, setCount] = useState<number>(3);
  const [questionType, setQuestionType] = useState<QuestionGenParams['question_type']>('mixed');

  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedMarkdown, setGeneratedMarkdown] = useState<string>('');

  // 师父指示 5：前端正则遮罩 (Answer Spoiler Mask)
  const [showAnswerSpoiler, setShowAnswerSpoiler] = useState(false);

  // 双栏作答台状态
  const [studentAnswers, setStudentAnswers] = useState<string>('1. \n2. \n3. ');
  const [isSubmittingQuiz, setIsSubmittingQuiz] = useState(false);
  const [quizFeedback, setQuizFeedback] = useState<string | null>(null);

  // 触发题目生成 (POST /v1/questions)
  const handleGenerateQuestions = async () => {
    if (!topic.trim() || isGenerating) return;
    setIsGenerating(true);
    setQuizFeedback(null);
    setShowAnswerSpoiler(false);
    try {
      const res = await fetch('/v1/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          difficulty,
          count,
          question_type: questionType,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setGeneratedMarkdown(data.text || '');
        // 自动初始化答题模板
        const template = Array.from({ length: count }, (_, i) => `${i + 1}. `).join('\n');
        setStudentAnswers(template);
      } else {
        const err = await res.text();
        alert(`题目生成失败: ${err}`);
      }
    } catch (e: any) {
      alert(`网络异常: ${e.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // 拆分题目主体与标准答案（正则切分）
  const splitQuestionAndAnswer = (md: string) => {
    const splitRegex = /(?:###\s*答案|##\s*参考答案|【答案】|---\s*\n*(?:答案|参考答案))/i;
    const match = md.search(splitRegex);
    if (match !== -1) {
      return {
        questionBody: md.slice(0, match).trim(),
        answerBody: md.slice(match).trim(),
      };
    }
    return {
      questionBody: md,
      answerBody: '',
    };
  };

  const { questionBody, answerBody } = splitQuestionAndAnswer(generatedMarkdown);

  // 提交作答并调用 LLM 批改 (POST /v1/quiz/grade)
  const handleSubmitQuiz = async () => {
    if (!studentAnswers.trim() || !generatedMarkdown.trim() || isSubmittingQuiz) return;
    setIsSubmittingQuiz(true);
    try {
      const res = await fetch('/v1/quiz/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          questions: generatedMarkdown,
          answers: studentAnswers,
        }),
      });
      if (res.ok) {
        const data: QuizGradeResponse = await res.json();
        setQuizFeedback(data.feedback);
      } else {
        const err = await res.text();
        alert(`作业批阅失败: ${err}`);
      }
    } catch (e: any) {
      alert(`提交批改失败: ${e.message}`);
    } finally {
      setIsSubmittingQuiz(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-bg font-mono text-xs">
      {/* 考点参数配置器 */}
      <div className="border border-border bg-surface p-4 rounded-sm space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border/50">
          <Wand2 className="w-4 h-4 text-accent" />
          <span className="font-bold uppercase tracking-label text-text-primary text-xs">
            考点靶向出题配置器 (AI_QUESTION_GENERATOR)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="sm:col-span-2 space-y-1">
            <label className="text-[10px] text-text-muted uppercase">学科 / 知识点主题 (TOPIC)</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：高中数学 导数极值、线性代数 特征值..."
              className="w-full bg-surface-2 border border-border p-2 text-xs text-text-primary focus:outline-none focus:border-accent"
            />
          </div>

          <div className="space-y-1">
            <label className="text-[10px] text-text-muted uppercase">难度等级 (DIFFICULTY)</label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as any)}
              className="w-full bg-surface-2 border border-border p-2 text-xs text-text-primary focus:outline-none focus:border-accent"
            >
              <option value="初学者">初学者 (基础)</option>
              <option value="中等">中等 (进阶)</option>
              <option value="拔高">拔高 (压轴)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] text-text-muted uppercase">题型 (TYPE)</label>
            <select
              value={questionType}
              onChange={(e) => setQuestionType(e.target.value as any)}
              className="w-full bg-surface-2 border border-border p-2 text-xs text-text-primary focus:outline-none focus:border-accent"
            >
              <option value="mixed">混合题型 (MIXED)</option>
              <option value="choice">单选题 (CHOICE)</option>
              <option value="fill">填空题 (FILL)</option>
              <option value="qa">解答题 (QA)</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2 text-text-muted">
            <span>出题数量:</span>
            <input
              type="number"
              min={1}
              max={10}
              value={count}
              onChange={(e) => setCount(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
              className="w-16 bg-surface-2 border border-border p-1 text-center text-text-primary focus:outline-none focus:border-accent"
            />
            <span className="text-[11px]">(1-10 题)</span>
          </div>

          <button
            onClick={handleGenerateQuestions}
            disabled={isGenerating || !topic.trim()}
            className="px-6 py-2 bg-accent active:bg-accent-active text-bg font-bold uppercase tracking-label rounded-xs flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4 fill-current" />}
            <span>GENERATE_PRACTICE_QUIZ</span>
          </button>
        </div>
      </div>

      {/* 师父指示 5：左右双栏作答台 */}
      {generatedMarkdown && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左栏：题目展示（含答案遮罩） */}
          <div className="border border-border bg-surface rounded-sm p-4 flex flex-col space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-border/60">
              <span className="font-bold uppercase text-accent text-xs tracking-wider">
                生成的练习试卷 (QUIZ_VIEWPORT)
              </span>
              {answerBody && (
                <button
                  onClick={() => setShowAnswerSpoiler(!showAnswerSpoiler)}
                  className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-2 border border-border hover:border-accent text-text-secondary hover:text-accent rounded-xs transition-colors text-[11px]"
                >
                  {showAnswerSpoiler ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  <span>{showAnswerSpoiler ? '遮罩标准答案' : 'REVEAL_STANDARD_ANSWERS'}</span>
                </button>
              )}
            </div>

            {/* 题干文本（已遮罩答案） */}
            <div className="flex-1 overflow-y-auto whitespace-pre-wrap leading-relaxed text-text-primary p-3 bg-surface-2 border border-border/50 rounded-xs max-h-[460px]">
              {questionBody}

              {/* 答案折叠区 */}
              {answerBody && showAnswerSpoiler && (
                <div className="mt-4 pt-4 border-t-2 border-dashed border-accent/40 bg-[#070707] p-3 rounded-xs text-[#4ADE80]">
                  <div className="font-bold uppercase text-accent mb-2">[STANDARD_ANSWERS & EXPLANATIONS]:</div>
                  {answerBody}
                </div>
              )}
            </div>
          </div>

          {/* 右栏：等宽作答编辑器与提交批阅 */}
          <div className="border border-border bg-surface rounded-sm p-4 flex flex-col space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-border/60">
              <span className="font-bold uppercase text-text-primary text-xs tracking-wider">
                在线作答台 (ANSWER_EDITOR)
              </span>
              <span className="text-[11px] text-text-muted">输入各题作答后提交 AI 批阅</span>
            </div>

            <textarea
              value={studentAnswers}
              onChange={(e) => setStudentAnswers(e.target.value)}
              rows={12}
              placeholder="在此输入您的各题答案，如：&#10;1. 选 A，求导后零点在 x=1&#10;2. 极大值为 4&#10;3. ..."
              className="flex-1 bg-surface-2 border border-border p-3 text-xs text-text-primary focus:outline-none focus:border-accent resize-none leading-relaxed font-bold"
            />

            <div className="flex items-center justify-end">
              <button
                onClick={handleSubmitQuiz}
                disabled={isSubmittingQuiz || !studentAnswers.trim()}
                className="px-5 py-2.5 bg-accent active:bg-accent-active text-bg font-bold uppercase tracking-label rounded-xs flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isSubmittingQuiz ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 fill-current" />
                )}
                <span>SUBMIT_QUIZ_FOR_GRADING</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 底部 AI 批阅反馈报告 */}
      {quizFeedback && (
        <div className="border border-border bg-surface rounded-sm p-4 space-y-3">
          <div className="flex items-center gap-2 text-[#4ADE80] font-bold text-xs uppercase tracking-wider pb-2 border-b border-border/60">
            <FileCheck className="w-4 h-4" />
            <span>AI 导师批阅反馈报告 (EVALUATION_REPORT)</span>
          </div>
          <div className="whitespace-pre-wrap leading-relaxed text-text-primary p-4 bg-surface-2 border border-border/60 rounded-xs">
            {quizFeedback}
          </div>
        </div>
      )}
    </div>
  );
};
