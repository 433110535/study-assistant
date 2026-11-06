import React, { useState } from 'react';
import { CodeEditorPanel } from '@/components/code/CodeEditorPanel';
import { SandboxTerminal } from '@/components/code/SandboxTerminal';
import { ProgressiveHintDrawer } from '@/components/code/ProgressiveHintDrawer';
import { AttemptsHistoryList } from '@/components/code/AttemptsHistoryList';
import { runCode } from '@/lib/api-client';
import { CodeRunResult, CodeTemplate, CODE_TEMPLATES } from '@/types/code';
import { Code2, Terminal, Lightbulb } from 'lucide-react';

export const CodePage: React.FC = () => {
  const [code, setCode] = useState<string>(CODE_TEMPLATES[0].code);
  const [tests, setTests] = useState<string>(CODE_TEMPLATES[0].tests);
  const [activeEditorTab, setActiveEditorTab] = useState<'main' | 'tests'>('main');
  const [timeoutS, setTimeoutS] = useState<number>(2.0);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runResult, setRunResult] = useState<CodeRunResult | null>(null);
  const [lastError, setLastError] = useState<string>('');
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  // Mobile sub-tab switcher for 390px screens
  const [mobileTab, setMobileTab] = useState<'editor' | 'terminal' | 'hints'>('editor');

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const res = await runCode(code, tests, threadId, timeoutS);
      setRunResult(res);
      setThreadId(res.thread_id);

      if (res.status !== 'passed' || res.stderr) {
        const obs = `状态: ${res.status}\n${
          res.stderr
            ? res.stderr.startsWith('Traceback')
              ? res.stderr
              : `信息: ${res.stderr}`
            : res.stdout
            ? `标准输出: ${res.stdout}`
            : `信息: ${res.status}`
        }`;
        setLastError(obs);
      } else {
        setLastError('');
      }

      // Increment refresh key to reload attempts history
      setRefreshKey((prev) => prev + 1);

      // On mobile, switch to terminal tab to see output
      if (window.innerWidth < 1024) {
        setMobileTab('terminal');
      }
    } catch (err: any) {
      alert(`沙箱执行接口异常: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectTemplate = (tpl: CodeTemplate) => {
    setCode(tpl.code);
    setTests(tpl.tests);
    setActiveEditorTab('main');
    setRunResult(null);
    setLastError('');
  };

  const handleRestoreCode = (restoredCode: string, restoredTests?: string) => {
    setCode(restoredCode);
    if (restoredTests !== undefined) {
      setTests(restoredTests);
    }
  };

  return (
    <div className="space-y-4 max-w-full overflow-x-hidden font-mono">
      {/* Page Header */}
      <div className="border-b border-[rgba(65,65,65,0.8)] pb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-[#FAFF69] tracking-widest uppercase">
            <span>[MODULE: M3 CODE TUTOR]</span>
            <span>•</span>
            <span>HARDENED WINDOWS JOB OBJECT SANDBOX</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white mt-1 uppercase">
            CODE TUTOR & ISOLATED SANDBOX WORKBENCH
          </h1>
          <p className="text-xs text-neutral-400 mt-0.5">
            64MB 提交内存硬限制、超时级联强杀、AST 静态安全过滤与苏格拉底式分级启发助教
          </p>
        </div>

        {/* Mobile View Toggle (hidden on desktop lg: 1024px+) */}
        <div className="flex lg:hidden items-center space-x-1 border border-[rgba(65,65,65,0.8)] p-1 bg-[#0A0A0A] text-xs">
          <button
            type="button"
            onClick={() => setMobileTab('editor')}
            className={`px-3 py-1 flex items-center space-x-1 ${
              mobileTab === 'editor'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>EDITOR</span>
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('terminal')}
            className={`px-3 py-1 flex items-center space-x-1 ${
              mobileTab === 'terminal'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>TERMINAL</span>
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('hints')}
            className={`px-3 py-1 flex items-center space-x-1 ${
              mobileTab === 'hints'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400'
            }`}
          >
            <Lightbulb className="w-3.5 h-3.5" />
            <span>HINTS</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Responsive 1440px (left 60%, right 40%), 1024px (stacked), 390px (mobile tabs) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Editor & Sandbox Terminal (7 cols = ~58-60%) */}
        <div
          className={`lg:col-span-7 space-y-4 ${
            mobileTab === 'hints' ? 'hidden lg:block' : 'block'
          }`}
        >
          {/* Editor Panel */}
          <div className={mobileTab === 'terminal' ? 'hidden lg:block' : 'block'}>
            <CodeEditorPanel
              code={code}
              onChangeCode={setCode}
              tests={tests}
              onChangeTests={setTests}
              onRun={handleRun}
              isRunning={isRunning}
              activeEditorTab={activeEditorTab}
              onSelectEditorTab={setActiveEditorTab}
              onSelectTemplate={handleSelectTemplate}
              timeoutS={timeoutS}
              onChangeTimeoutS={setTimeoutS}
            />
          </div>

          {/* Terminal Panel */}
          <div className={mobileTab === 'editor' ? 'hidden lg:block' : 'block'}>
            <SandboxTerminal
              result={runResult}
              isRunning={isRunning}
              onSendErrorToHints={(err) => {
                setLastError(err);
                if (window.innerWidth < 1024) setMobileTab('hints');
              }}
            />
          </div>
        </div>

        {/* Right Column: Progressive Hints & Execution Attempts (5 cols = ~40-42%) */}
        <div
          className={`lg:col-span-5 space-y-4 ${
            mobileTab !== 'hints' ? 'hidden lg:block' : 'block'
          }`}
        >
          {/* Progressive Hint Drawer */}
          <ProgressiveHintDrawer
            key={lastError || 'clean'}
            lastError={lastError}
            currentCode={code}
          />

          {/* Execution Attempts History */}
          <AttemptsHistoryList
            threadId={threadId}
            onRestoreCode={handleRestoreCode}
            refreshKey={refreshKey}
          />
        </div>
      </div>
    </div>
  );
};
export default CodePage;
