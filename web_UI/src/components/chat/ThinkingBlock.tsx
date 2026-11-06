import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Terminal } from 'lucide-react';

interface ThinkingBlockProps {
  thinking: string;
  isStreaming?: boolean;
}

export const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ thinking, isStreaming = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!thinking) return null;

  return (
    <div className="mb-3 border border-border bg-surface-2 rounded-sm overflow-hidden font-mono text-xs">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-surface hover:bg-surface-2 text-text-secondary transition-colors text-left select-none"
      >
        <div className="flex items-center gap-2">
          <Terminal className={`w-3.5 h-3.5 ${isStreaming ? 'text-accent' : 'text-text-muted'}`} />
          <span className="font-bold tracking-label uppercase text-[11px] text-accent">
            {isStreaming ? 'THINKING_STREAM :: RUNNING' : 'THINKING_LOG :: COMPLETED'}
          </span>
          {isStreaming && (
            <span className="inline-block w-1.5 h-1.5 bg-accent rounded-none animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-1 text-text-muted text-[11px]">
          <span>{isExpanded ? '收起' : '展开'}</span>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 text-text-muted whitespace-pre-wrap leading-relaxed border-t border-border/50 text-[11px] max-h-56 overflow-y-auto bg-[#070707]">
          {thinking}
          {isStreaming && (
            <span className="inline-block w-2 h-3.5 bg-accent ml-1 animate-pulse align-middle" />
          )}
        </div>
      )}
    </div>
  );
};
