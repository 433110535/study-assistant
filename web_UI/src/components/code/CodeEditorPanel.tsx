import React, { useRef } from 'react';
import { Play, RotateCcw, FileCode, CheckSquare, Sparkles } from 'lucide-react';
import { CodeTemplate, CODE_TEMPLATES } from '@/types/code';


interface CodeEditorPanelProps {
  code: string;
  onChangeCode: (code: string) => void;
  tests: string;
  onChangeTests: (tests: string) => void;
  onRun: () => void;
  isRunning: boolean;
  activeEditorTab: 'main' | 'tests';
  onSelectEditorTab: (tab: 'main' | 'tests') => void;
  onSelectTemplate: (tpl: CodeTemplate) => void;
  timeoutS: number;
  onChangeTimeoutS: (s: number) => void;
}

export const CodeEditorPanel: React.FC<CodeEditorPanelProps> = ({
  code,
  onChangeCode,
  tests,
  onChangeTests,
  onRun,
  isRunning,
  activeEditorTab,
  onSelectEditorTab,
  onSelectTemplate,
  timeoutS,
  onChangeTimeoutS,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);

  const currentContent = activeEditorTab === 'main' ? code : tests;
  const currentSetter = activeEditorTab === 'main' ? onChangeCode : onChangeTests;

  // Sync gutter scroll with textarea
  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (gutterRef.current) {
      gutterRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  React.useEffect(() => {
    if (gutterRef.current && textareaRef.current) {
      gutterRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, [activeEditorTab, currentContent]);

  // Handle Tab key (insert 4 spaces) & Ctrl+Enter (run)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const ta = e.currentTarget;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const val = ta.value;
      const nextVal = val.substring(0, start) + '    ' + val.substring(end);
      currentSetter(nextVal);
      // Restore cursor position
      setTimeout(() => {
        ta.selectionStart = ta.selectionEnd = start + 4;
      }, 0);
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!isRunning) onRun();
    }
  };

  const lineCount = Math.max(12, currentContent.split('\n').length);
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1);

  return (
    <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] flex flex-col font-mono text-sm">
      {/* Editor Header Toolbar */}
      <div className="p-2.5 border-b border-[rgba(65,65,65,0.8)] bg-black flex flex-wrap items-center justify-between gap-2">
        {/* Dual Tab Switcher */}
        <div className="flex items-center space-x-1">
          <button
            type="button"
            onClick={() => onSelectEditorTab('main')}
            className={`px-3 py-1 text-xs uppercase tracking-wider flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeEditorTab === 'main'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white border border-[rgba(65,65,65,0.8)]'
            }`}
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>MAIN_SCRIPT.py</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectEditorTab('tests')}
            className={`px-3 py-1 text-xs uppercase tracking-wider flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeEditorTab === 'tests'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white border border-[rgba(65,65,65,0.8)]'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>TEST_ASSERT.py {tests.trim() ? '(ACTIVE)' : ''}</span>
          </button>
        </div>

        {/* Preset Templates Selector & Controls */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 text-xs text-neutral-400">
            <Sparkles className="w-3 h-3 text-[#FAFF69]" />
            <select
              aria-label="预设模板"
              onChange={(e) => {
                const found = CODE_TEMPLATES.find((t) => t.id === e.target.value);
                if (found) onSelectTemplate(found);
              }}
              className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] px-2 py-1 text-xs text-neutral-200 focus:outline-none focus:border-[#FAFF69]"
              defaultValue=""
            >
              <option value="" disabled>
                PRESET_ALGORITHMS / 预设教学模板
              </option>
              {CODE_TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>
                  [{t.category}] {t.title}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-1 text-xs text-neutral-400">
            <span className="text-[10px] text-neutral-500">TIMEOUT:</span>
            <select
              aria-label="超时时间"
              value={timeoutS}
              onChange={(e) => onChangeTimeoutS(Number(e.target.value))}
              className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] px-1.5 py-1 text-xs text-neutral-200 focus:outline-none"
            >
              <option value={1}>1.0s</option>
              <option value={2}>2.0s</option>
              <option value={5}>5.0s</option>
            </select>
          </div>

          {/* Run Button */}
          <button
            type="button"
            disabled={isRunning}
            onClick={onRun}
            className="px-4 py-1.5 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110 disabled:opacity-50 flex items-center space-x-1.5 cursor-pointer shadow-sm"
          >
            {isRunning ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>SANDBOX_EXECUTING...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>RUN (Ctrl+Enter)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Editor Body with Gutter */}
      <div className="flex flex-1 min-h-[340px] max-h-[500px] overflow-hidden bg-[#0A0A0A]">
        {/* Line Gutter */}
        <div
          ref={gutterRef}
          aria-hidden="true"
          className="w-12 py-3 pr-2 select-none text-right font-mono text-xs text-neutral-600 bg-black/40 border-r border-[rgba(65,65,65,0.8)] leading-6 overflow-hidden pointer-events-none"
        >
          {lineNumbers.map((num) => (
            <div key={num}>{num}</div>
          ))}
        </div>

        {/* Text Area */}
        <textarea
          ref={textareaRef}
          aria-label={activeEditorTab === 'main' ? '主程序代码编辑器' : '测试断言代码编辑器'}
          value={currentContent}
          onChange={(e) => currentSetter(e.target.value)}
          onKeyDown={handleKeyDown}
          onScroll={handleScroll}
          spellCheck={false}
          className="flex-1 p-3 bg-transparent text-xs font-mono text-neutral-100 resize-none focus:outline-none leading-6 whitespace-pre overflow-auto selection:bg-[#FAFF69]/20"
          placeholder={
            activeEditorTab === 'main'
              ? '# 输入 Python 代码，支持定义函数与标准输出 print...\n# 按 Tab 插入 4 空格缩进，按 Ctrl+Enter 立即在沙箱执行'
              : '# 输入针对主程序的 assert 断言校验脚本 (可选)...\nassert solution(5) == 120, "Assertion failed!"'
          }
        />
      </div>

      {/* Bottom Status Ribbon */}
      <div className="px-3 py-1.5 bg-black border-t border-[rgba(65,65,65,0.8)] flex items-center justify-between text-[10px] text-neutral-500">
        <div className="flex items-center space-x-3">
          <span>PYTHON 3.10 SANDBOX</span>
          <span>•</span>
          <span>MEMORY_LIMIT: 64MB HARD_CAP</span>
          <span>•</span>
          <span>JOB_OBJECT_ISOLATED</span>
        </div>
        <div className="text-neutral-400">
          LINES: {currentContent.split('\n').length} | BYTES: {new Blob([currentContent]).size} B
        </div>
      </div>
    </div>
  );
};
