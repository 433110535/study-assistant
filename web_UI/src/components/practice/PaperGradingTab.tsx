import React, { useState, useRef } from 'react';
import {
  FileText,
  Upload,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Ban,
  Loader2,
  ChevronRight,
  X,
  BookOpen,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { PaperGradeResponse, PaperGradeItem, GradeStatus, SingleItemGradeResponse } from '@/types/practice';

interface PaperGradingTabProps {
  onOpenInSingleLab: (question: string, studentAnswer: string) => void;
  onNavigateToMistakes?: () => void;
}

export const PaperGradingTab: React.FC<PaperGradingTabProps> = ({
  onOpenInSingleLab,
  onNavigateToMistakes,
}) => {
  const [paperText, setPaperText] = useState('');
  const [enhanced, setEnhanced] = useState(true);
  const [autoCollect, setAutoCollect] = useState(true);
  const [subject, setSubject] = useState('数学');
  const [isOcrLoading, setIsOcrLoading] = useState(false);
  const [ocrStatus, setOcrStatus] = useState<string | null>(null);

  const [isGrading, setIsGrading] = useState(false);
  const [gradeResult, setGradeResult] = useState<PaperGradeResponse | null>(null);

  // 单题深度诊断抽屉状态与缓存
  const [selectedItem, setSelectedItem] = useState<PaperGradeItem | null>(null);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [diagnosisCache, setDiagnosisCache] = useState<Record<number, SingleItemGradeResponse>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  // OCR 识别处理
  const handleOcrFile = async (file: File) => {
    if (!file.type.startsWith('image/')) return;
    setIsOcrLoading(true);
    setOcrStatus('[OCR_SCANNING...] 正在识别试卷题目与作答...');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('focus', '全部');

      const res = await fetch('/v1/vision/ocr', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.text) {
          setPaperText(data.text);
          setOcrStatus(`识别成功 (${data.model || 'qwen-vl'} · ${data.elapsed_ms || 0}ms)`);
        }
      } else {
        const err = await res.text();
        setOcrStatus(`OCR 异常: ${err}`);
      }
    } catch (e: any) {
      setOcrStatus(`OCR 失败: ${e.message}`);
    } finally {
      setIsOcrLoading(false);
    }
  };

  // 支持剪贴板直接粘贴图片
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          void handleOcrFile(file);
          break;
        }
      }
    }
  };

  // 执行整卷判分
  const handleExecuteGrading = async () => {
    if (!paperText.trim() || isGrading) return;
    setIsGrading(true);
    try {
      const res = await fetch('/v1/papers/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: paperText,
          enhanced,
          auto_collect_mistakes: autoCollect,
          subject,
        }),
      });
      if (res.ok) {
        const data: PaperGradeResponse = await res.json();
        setGradeResult(data);
      } else {
        const err = await res.text();
        alert(`判卷失败 [${res.status}]: ${err}`);
      }
    } catch (e: any) {
      alert(`网络请求异常: ${e.message}`);
    } finally {
      setIsGrading(false);
    }
  };

  // 点击题目行打开深度诊断抽屉
  const handleItemClick = async (item: PaperGradeItem) => {
    setSelectedItem(item);
    if (item.status === 'correct' || item.status === 'ungraded' || item.status === 'unsupported') {
      return;
    }

    // 检查缓存
    if (diagnosisCache[item.item_no]) {
      return;
    }

    setIsDiagnosing(true);
    try {
      const res = await fetch('/v1/items/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: item.question,
          student: item.student_answer,
          correct: item.correct_answer,
        }),
      });
      if (res.ok) {
        const data: SingleItemGradeResponse = await res.json();
        setDiagnosisCache((prev) => ({ ...prev, [item.item_no]: data }));
      }
    } catch (e) {
      console.error('Failed to diagnose item:', e);
    } finally {
      setIsDiagnosing(false);
    }
  };

  // 状态胶囊渲染
  const renderStatusBadge = (status: GradeStatus) => {
    switch (status) {
      case 'correct':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono font-bold uppercase rounded-xs bg-[#4ADE80]/10 border border-[#4ADE80]/40 text-[#4ADE80]">
            <CheckCircle2 className="w-3 h-3" /> [PASS / CORRECT]
          </span>
        );
      case 'incorrect':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono font-bold uppercase rounded-xs bg-[#F87171]/10 border border-[#F87171]/40 text-[#F87171]">
            <AlertCircle className="w-3 h-3" /> [FAIL / INCORRECT]
          </span>
        );
      case 'partial':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono font-bold uppercase rounded-xs bg-accent/10 border border-accent/40 text-accent">
            [PARTIAL]
          </span>
        );
      case 'ungraded':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono uppercase rounded-xs bg-surface border border-dashed border-[#52525B] text-[#A1A1AA]">
            <HelpCircle className="w-3 h-3" /> [UNGRADED]
          </span>
        );
      case 'unsupported':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono uppercase rounded-xs bg-[#0A0A0A] border border-dashed border-[#3F3F46] text-[#71717A]">
            <Ban className="w-3 h-3" /> [UNSUPPORTED]
          </span>
        );
    }
  };

  const activeDiagnosis = selectedItem ? diagnosisCache[selectedItem.item_no] : null;

  return (
    <div className="flex-1 flex overflow-hidden font-mono text-xs relative">
      {/* 主工作区 */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-bg">
        {/* 输入控制台 */}
        <div className="border border-border bg-surface p-4 rounded-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-accent" />
              <span className="font-bold uppercase tracking-label text-text-primary text-xs">
                试卷源码输入与 OCR 提取 (PAPER_SOURCE)
              </span>
            </div>
            {ocrStatus && (
              <span className="text-[11px] text-accent font-bold">{ocrStatus}</span>
            )}
          </div>

          <div className="relative">
            <textarea
              value={paperText}
              onChange={(e) => setPaperText(e.target.value)}
              onPaste={handlePaste}
              rows={6}
              placeholder="在此粘贴整卷文本（支持题号、学生作答与标准答案），或直接按 Ctrl+V 粘贴试卷截图自动触发 OCR 提取..."
              className="w-full bg-surface-2 border border-border p-3 text-xs text-text-primary focus:outline-none focus:border-accent resize-y font-mono leading-relaxed"
            />
          </div>

          {/* 工具栏与参数配置 */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border/50">
            <div className="flex items-center gap-4">
              <input
                type="file"
                ref={fileInputRef}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleOcrFile(f);
                }}
                accept="image/*"
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isOcrLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 border border-border hover:border-accent text-text-secondary hover:text-accent rounded-xs transition-colors"
              >
                {isOcrLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                ) : (
                  <ImageIcon className="w-3.5 h-3.5" />
                )}
                <span>上传试卷图片</span>
              </button>

              <label className="flex items-center gap-1.5 text-text-secondary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={enhanced}
                  onChange={(e) => setEnhanced(e.target.checked)}
                  className="accent-[#FAFF69]"
                />
                <span>增强模式 (多选/多空/单位等效)</span>
              </label>

              <label className="flex items-center gap-1.5 text-text-secondary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoCollect}
                  onChange={(e) => setAutoCollect(e.target.checked)}
                  className="accent-[#FAFF69]"
                />
                <span>自动归因入错题本并更新掌握度</span>
              </label>

              <div className="flex items-center gap-1 text-text-muted">
                <span>学科:</span>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-16 px-1.5 py-0.5 bg-surface-2 border border-border text-text-primary text-xs text-center rounded-xs focus:outline-none focus:border-accent"
                />
              </div>
            </div>

            <button
              onClick={handleExecuteGrading}
              disabled={isGrading || !paperText.trim()}
              className="px-5 py-2 bg-accent active:bg-accent-active text-bg font-bold uppercase tracking-label rounded-xs flex items-center gap-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isGrading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 fill-current" />
              )}
              <span>EXECUTE_PAPER_GRADING</span>
            </button>
          </div>
        </div>

        {/* 汇总遥测面板 (Summary Telemetry Bar) */}
        {gradeResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="p-3 bg-surface border border-border rounded-xs">
                <div className="text-[10px] text-text-muted uppercase">题目总数 TOTAL</div>
                <div className="text-xl font-bold text-text-primary mt-1">{gradeResult.total}</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-xs">
                <div className="text-[10px] text-text-muted uppercase">已判题数 GRADED</div>
                <div className="text-xl font-bold text-accent mt-1">{gradeResult.graded}</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-xs">
                <div className="text-[10px] text-text-muted uppercase">正确 CORRECT</div>
                <div className="text-xl font-bold text-[#4ADE80] mt-1">{gradeResult.correct}</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-xs">
                <div className="text-[10px] text-text-muted uppercase">错误 INCORRECT</div>
                <div className="text-xl font-bold text-[#F87171] mt-1">{gradeResult.incorrect}</div>
              </div>
              <div className="p-3 bg-surface border border-border rounded-xs">
                <div className="text-[10px] text-text-muted uppercase">未判 UNGRADED</div>
                <div className="text-xl font-bold text-text-muted mt-1">{gradeResult.ungraded}</div>
              </div>
            </div>

            {/* 师父指示 4：自动入库错题横幅 */}
            {gradeResult.collected_count && gradeResult.collected_count > 0 ? (
              <div className="p-3 bg-surface-2 border border-accent rounded-xs flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-text-primary">
                  <Sparkles className="w-4 h-4 text-accent" />
                  <span className="font-bold text-accent">
                    AUTO_COLLECTED: {gradeResult.collected_count} MISTAKES
                  </span>
                  <span className="text-text-muted">
                    -&gt; [{gradeResult.collected_mistake_ids?.join(', ')}] | MASTERY_UPDATED
                  </span>
                </div>
                {onNavigateToMistakes && (
                  <button
                    onClick={onNavigateToMistakes}
                    className="flex items-center gap-1 text-accent hover:underline font-bold text-[11px]"
                  >
                    <span>[VIEW_IN_MISTAKE_BOOK -&gt;]</span>
                  </button>
                )}
              </div>
            ) : null}

            {/* 题目表格 */}
            <div className="border border-border bg-surface rounded-sm overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-[10px] text-text-muted uppercase tracking-wider">
                    <th className="p-3 w-16">题号</th>
                    <th className="p-3">题目题干</th>
                    <th className="p-3 w-28">学生作答</th>
                    <th className="p-3 w-28">标准答案</th>
                    <th className="p-3 w-36">判定状态</th>
                    <th className="p-3 w-32 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {gradeResult.items.map((it) => (
                    <tr
                      key={it.item_no}
                      onClick={() => handleItemClick(it)}
                      className={`hover:bg-surface-2 cursor-pointer transition-colors ${
                        selectedItem?.item_no === it.item_no ? 'bg-surface-2' : ''
                      }`}
                    >
                      <td className="p-3 font-bold text-accent">#{it.item_no}</td>
                      <td className="p-3 truncate max-w-xs text-text-primary" title={it.question}>
                        {it.question}
                      </td>
                      <td className="p-3 font-bold text-text-secondary">{it.student_answer || '-'}</td>
                      <td className="p-3 text-text-muted">{it.correct_answer || '-'}</td>
                      <td className="p-3">{renderStatusBadge(it.status)}</td>
                      <td className="p-3 text-right">
                        {(it.status === 'ungraded' || it.status === 'unsupported') ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenInSingleLab(it.question, it.student_answer);
                            }}
                            className="text-[10px] text-accent hover:underline flex items-center gap-1 ml-auto"
                          >
                            <span>[OPEN_IN_SINGLE_LAB -&gt;]</span>
                          </button>
                        ) : (
                          <span className="text-[10px] text-text-muted flex items-center gap-1 justify-end">
                            <span>诊断</span>
                            <ChevronRight className="w-3 h-3" />
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 右侧单题深度诊断抽屉 (340px) */}
      {selectedItem && (
        <aside className="w-80 md:w-96 border-l border-border bg-surface flex flex-col h-full shrink-0">
          <div className="h-12 px-4 border-b border-border flex items-center justify-between bg-surface-2">
            <span className="font-bold text-accent uppercase text-[11px] tracking-label">
              ITEM #{selectedItem.item_no} DIAGNOSIS
            </span>
            <button
              onClick={() => setSelectedItem(null)}
              className="p-1 text-text-muted hover:text-text-primary rounded-xs"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="space-y-1">
              <div className="text-[10px] text-text-muted uppercase">原题题干</div>
              <p className="p-2.5 bg-surface-2 border border-border rounded-xs text-text-primary leading-relaxed">
                {selectedItem.question}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <div className="text-[10px] text-text-muted uppercase">学生作答</div>
                <div className="p-2 bg-surface-2 border border-border rounded-xs font-bold text-text-primary">
                  {selectedItem.student_answer || '无作答'}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-[10px] text-text-muted uppercase">标准答案</div>
                <div className="p-2 bg-surface-2 border border-border rounded-xs font-bold text-[#4ADE80]">
                  {selectedItem.correct_answer || '无标准答案'}
                </div>
              </div>
            </div>

            {/* 深度归因与变式题 */}
            {isDiagnosing ? (
              <div className="p-8 text-center text-text-muted space-y-2">
                <Loader2 className="w-5 h-5 animate-spin mx-auto text-accent" />
                <div className="text-[11px]">正在分析错因与生成考点变式...</div>
              </div>
            ) : activeDiagnosis?.diagnosed ? (
              <div className="space-y-3 pt-2 border-t border-border">
                <div className="p-3 bg-surface-2 border border-border/80 rounded-xs space-y-1.5">
                  <div className="text-[10px] text-accent uppercase font-bold flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>错因归因诊断 (ERROR_DIAGNOSIS)</span>
                  </div>
                  <div className="text-xs text-text-primary">
                    考点: <span className="font-bold text-accent">{activeDiagnosis.diagnosed.concept}</span>
                  </div>
                  <div className="text-xs text-[#F87171]">
                    类型: <span className="font-bold">{activeDiagnosis.diagnosed.error_type}</span>
                  </div>
                  {activeDiagnosis.diagnosed.explanation && (
                    <p className="text-[11px] text-text-muted mt-1 leading-relaxed">
                      {activeDiagnosis.diagnosed.explanation}
                    </p>
                  )}
                </div>

                {activeDiagnosis.variants && activeDiagnosis.variants.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] text-text-muted uppercase flex items-center gap-1">
                      <BookOpen className="w-3.5 h-3.5 text-accent" />
                      <span>同考点推荐变式题 ({activeDiagnosis.variants.length})</span>
                    </div>
                    {activeDiagnosis.variants.map((v, i) => (
                      <div
                        key={i}
                        className="p-2.5 bg-surface-2 border border-border/60 rounded-xs text-[11px] text-text-secondary leading-relaxed"
                      >
                        <div className="text-accent font-bold text-[10px] mb-1">变式 #{i + 1}</div>
                        {v}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : selectedItem.status === 'correct' ? (
              <div className="p-4 bg-surface-2 border border-[#4ADE80]/30 rounded-xs text-[#4ADE80] text-center text-xs">
                本题判定正确，无需错因归因。
              </div>
            ) : (
              <div className="p-4 bg-surface-2 border border-border rounded-xs text-text-muted text-center text-xs">
                暂无诊断信息。您可点击下方按钮在单题实验室中手动精调判分。
                <button
                  onClick={() => onOpenInSingleLab(selectedItem.question, selectedItem.student_answer)}
                  className="mt-3 px-3 py-1.5 bg-surface border border-accent text-accent font-bold rounded-xs flex items-center gap-1 mx-auto"
                >
                  <span>转到单题对照实验室</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
};
