import React from 'react';
import { Terminal, CheckCircle2, XCircle, AlertTriangle, ShieldAlert, ArrowRight } from 'lucide-react';
import { CodeRunResult, CodeSandboxStatus } from '@/types/code';

interface SandboxTerminalProps {
  result: CodeRunResult | null;
  isRunning: boolean;
  onSendErrorToHints?: (errorText: string) => void;
}

export const SandboxTerminal: React.FC<SandboxTerminalProps> = ({
  result,
  isRunning,
  onSendErrorToHints,
}) => {
  const getStatusBadge = (status: CodeSandboxStatus, timedOut: boolean) => {
    if (timedOut || status === 'timeout') {
      return (
        <span className="px-2 py-0.5 border border-[#FAFF69] bg-[#FAFF69]/10 text-[#FAFF69] text-xs font-bold flex items-center space-x-1">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>[STATUS: TLE / TIMEOUT_KILLED]</span>
        </span>
      );
    }
    if (status === 'memory' || status === 'memory_limit') {
      return (
        <span className="px-2 py-0.5 border border-red-500 bg-red-950/30 text-red-400 text-xs font-bold flex items-center space-x-1">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>[STATUS: MLE / OOM_64MB_LIMIT]</span>
        </span>
      );
    }
    if (status === 'rejected' || status === 'security_violation') {
      return (
        <span className="px-2 py-0.5 border border-red-500 bg-red-950/30 text-red-400 text-xs font-bold flex items-center space-x-1">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>[STATUS: 403 / SECURITY_VIOLATION]</span>
        </span>
      );
    }
    if (status === 'passed') {
      return (
        <span className="px-2 py-0.5 border border-[#4ADE80] bg-[#4ADE80]/10 text-[#4ADE80] text-xs font-bold flex items-center space-x-1">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>[STATUS: 0 / OK_PASSED]</span>
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 border border-red-500 bg-red-950/30 text-red-400 text-xs font-bold flex items-center space-x-1">
        <XCircle className="w-3.5 h-3.5" />
        <span>[STATUS: 1 / EXECUTION_FAILED]</span>
      </span>
    );
  };

  const hasError = result && (result.status !== 'passed' || !!result.stderr);

  return (
    <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] font-mono text-sm flex flex-col">
      {/* Terminal Title Bar with Telemetry */}
      <div className="p-2.5 border-b border-[rgba(65,65,65,0.8)] bg-black flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-[#FAFF69]" />
          <span className="text-xs text-white font-bold tracking-wider">
            SANDBOX_TERMINAL_OUTPUT
          </span>
          {result && getStatusBadge(result.status, result.timed_out)}
        </div>

        {result && (
          <div className="flex items-center space-x-3 text-[10px] text-neutral-400">
            <span>ELAPSED: {result.duration_ms} ms</span>
            <span>•</span>
            <span>EXIT_CODE: {result.exit_code}</span>
            <span>•</span>
            <span className="text-neutral-500">THREAD: [{result.thread_id.slice(0, 8)}]</span>
          </div>
        )}
      </div>

      {/* Terminal Body */}
      <div className="p-4 bg-black min-h-[160px] max-h-[300px] overflow-y-auto space-y-3 select-text">
        {isRunning ? (
          <div className="flex items-center space-x-2 text-xs text-[#FAFF69] animate-pulse">
            <span className="inline-block w-2 h-2 bg-[#FAFF69]" />
            <span>SANDBOX_JOB_OBJECT_RUNNING: EXEC_IN_PROGRESS...</span>
          </div>
        ) : !result ? (
          <div className="text-neutral-600 text-xs space-y-1">
            <div>// 点击上方「RUN (Ctrl+Enter)」将代码发送至 Windows 硬化隔离沙箱运行</div>
            <div>// 沙箱配置：64MB 内存硬限制、超时强杀、AST 敏感模块屏蔽</div>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Standard Output (STDOUT) */}
            {result.stdout ? (
              <div className="space-y-1">
                <div className="text-[10px] text-neutral-500 font-bold uppercase tracking-wider">
                  [STDOUT / 标准输出]:
                </div>
                <pre className="text-xs text-neutral-200 whitespace-pre-wrap break-all font-mono leading-relaxed">
                  {result.stdout}
                </pre>
              </div>
            ) : null}

            {/* Standard Error / Traceback (STDERR) */}
            {result.stderr ? (
              <div className="space-y-1 pt-2 border-t border-neutral-800">
                <div className="text-[10px] text-red-400 font-bold uppercase tracking-wider flex items-center space-x-1">
                  <AlertTriangle className="w-3 h-3 text-red-400" />
                  <span>[STDERR / TRACEBACK 异常]:</span>
                </div>
                <pre className="text-xs text-red-400 whitespace-pre-wrap break-all font-mono leading-relaxed bg-red-950/20 p-2.5 border border-red-900/60">
                  {result.stderr}
                </pre>
              </div>
            ) : null}

            {/* Neither stdout nor stderr */}
            {!result.stdout && !result.stderr && (
              <div className="text-xs text-neutral-400">
                [PROCESS_EXITED_WITH_NO_STDOUT_OUTPUT]
              </div>
            )}
          </div>
        )}
      </div>

      {/* Terminal Footer with Hint Transfer Action */}
      {hasError && onSendErrorToHints && (
        <div className="p-2.5 bg-[#0A0A0A] border-t border-[rgba(65,65,65,0.8)] flex items-center justify-between">
          <span className="text-[10px] text-neutral-400">
            检测到沙箱执行未通过，可直接将当前 Traceback 发送给分级启发助教：
          </span>
          <button
            type="button"
            onClick={() => {
              if (!result) return;
              const obs = `状态: ${result.status}\n${
                result.stderr
                  ? result.stderr.startsWith('Traceback')
                    ? result.stderr
                    : `信息: ${result.stderr}`
                  : result.stdout
                  ? `标准输出: ${result.stdout}`
                  : `信息: ${result.status}`
              }`;
              onSendErrorToHints(obs);
            }}
            className="px-3 py-1 border border-[#FAFF69] text-[#FAFF69] hover:bg-[#FAFF69] hover:text-black text-xs font-bold uppercase tracking-wider flex items-center space-x-1 cursor-pointer transition-colors"
          >
            <span>SEND_ERROR_TO_HINTS</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
