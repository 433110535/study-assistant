import React, { useState } from 'react';
import { Terminal, CheckCircle2, AlertCircle, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import { ToolCallInfo } from '@/types/chat';

interface ToolCallCardProps {
  toolCall: ToolCallInfo;
}

export const ToolCallCard: React.FC<ToolCallCardProps> = ({ toolCall }) => {
  const [isOpen, setIsOpen] = useState(false);

  const isCalling = toolCall.status === 'calling';
  const isError = toolCall.status === 'error';

  return (
    <div className="mb-2 border border-border bg-surface-2 rounded-sm overflow-hidden font-mono text-xs">
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between px-3 py-2 bg-surface cursor-pointer hover:bg-surface-2 transition-colors select-none"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Terminal className="w-3.5 h-3.5 text-accent shrink-0" />
          <span className="font-bold text-accent text-[11px] truncate uppercase tracking-label">
            EXEC :: {toolCall.name}
          </span>
          {toolCall.iteration ? (
            <span className="text-[10px] text-text-muted px-1 bg-surface border border-border rounded-xs">
              #{toolCall.iteration}
            </span>
          ) : null}
          {isCalling ? (
            <span className="flex items-center gap-1 text-[10px] text-bg bg-accent font-bold px-1.5 py-0.2 rounded-xs">
              <Loader2 className="w-3 h-3 animate-spin" />
              RUNNING
            </span>
          ) : isError ? (
            <span className="flex items-center gap-1 text-[10px] text-danger border border-danger/40 px-1.5 py-0.2 rounded-xs">
              <AlertCircle className="w-3 h-3" />
              FAILED
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] text-success border border-success/40 px-1.5 py-0.2 rounded-xs">
              <CheckCircle2 className="w-3 h-3" />
              DONE
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-text-muted text-[11px] shrink-0">
          <span>{isOpen ? '折叠' : '详情'}</span>
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </div>

      {isOpen && (
        <div className="p-3 border-t border-border/50 text-[11px] space-y-2 bg-[#050505]">
          <div>
            <div className="text-text-muted uppercase text-[10px] tracking-wider mb-1">Tool Arguments:</div>
            <pre className="p-2 bg-surface border border-border/60 rounded-xs text-text-secondary overflow-x-auto text-[11px] max-h-40 overflow-y-auto">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <div className="text-text-muted uppercase text-[10px] tracking-wider mb-1">Execution Output:</div>
              <pre className="p-2 bg-surface border border-border/60 rounded-xs text-text-muted overflow-x-auto max-h-40 overflow-y-auto text-[11px] whitespace-pre-wrap">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
