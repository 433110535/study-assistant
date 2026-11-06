import React, { useEffect, useRef } from 'react';
import { Activity, X, Terminal, Sparkles, Database } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { ToolCallCard } from './ToolCallCard';
import { ThinkingBlock } from './ThinkingBlock';

interface ReActInspectorProps {
  currentMessage: ChatMessage | null;
  isOpen: boolean;
  onClose: () => void;
  isStreaming: boolean;
}

export const ReActInspector: React.FC<ReActInspectorProps> = ({
  currentMessage,
  isOpen,
  onClose,
  isStreaming,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // 师父指示：瞬时吸底定位，避免 smooth 滚动堆积
  useEffect(() => {
    if (isStreaming && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [isStreaming, currentMessage?.thinking, currentMessage?.toolCalls]);

  if (!isOpen) return null;

  const toolCalls = currentMessage?.toolCalls || [];
  const thinking = currentMessage?.thinking || '';
  const isHistorical = currentMessage?.isHistorical;

  return (
    <aside className="w-80 border-l border-border bg-surface flex flex-col h-full shrink-0 transition-all font-mono text-xs">
      {/* 顶部标题栏 */}
      <div className="h-12 px-3 border-b border-border flex items-center justify-between bg-surface-2">
        <div className="flex items-center gap-2">
          <Activity className={`w-4 h-4 ${isStreaming ? 'text-accent' : 'text-text-muted'}`} />
          <span className="font-bold tracking-label uppercase text-[11px] text-text-primary">
            REACT TRACE INSPECTOR
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-text-secondary hover:text-text-primary rounded-xs hover:bg-surface"
          title="关闭轨迹面板"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 状态统计条 */}
      <div className="p-3 border-b border-border bg-[#050505] text-[11px] flex items-center justify-between text-text-muted">
        <div>
          状态:{' '}
          <span className={isStreaming ? 'text-accent font-bold' : 'text-text-secondary'}>
            {isStreaming ? 'STREAMING' : 'IDLE'}
          </span>
        </div>
        <div>
          工具调用: <span className="text-text-primary font-bold">{toolCalls.length}</span> 次
        </div>
      </div>

      {/* 轨迹主体滚动区 */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* 师父指示：历史持久化消息无遥测数据时的优雅降级 */}
        {isHistorical && !thinking && toolCalls.length === 0 ? (
          <div className="p-4 border border-border/60 bg-[#080808] rounded-sm text-text-muted text-center space-y-2 mt-4">
            <Database className="w-6 h-6 mx-auto text-text-muted/40" />
            <div className="text-[11px] text-accent font-bold uppercase tracking-label">
              NO_TELEMETRY_RECORDED_FOR_HISTORICAL_MESSAGE
            </div>
            <p className="text-[10px] text-text-muted leading-relaxed">
              该会话记录来自持久化历史库，底层 SQLite 仅存储对话文本，未记录 ReAct 内部工具流。实时对话中将提供全量推理轨迹。
            </p>
          </div>
        ) : (
          <>
            {thinking && (
              <div>
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-accent" />
                  <span>推理思考流 (Thought)</span>
                </div>
                <ThinkingBlock thinking={thinking} isStreaming={isStreaming} />
              </div>
            )}

            {toolCalls.length > 0 ? (
              <div>
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Terminal className="w-3 h-3 text-accent" />
                  <span>工具调用日志 (Action & Observation)</span>
                </div>
                {toolCalls.map((tc) => (
                  <ToolCallCard key={tc.id} toolCall={tc} />
                ))}
              </div>
            ) : !thinking && (
              <div className="h-48 flex flex-col items-center justify-center text-text-muted text-center p-4">
                <Terminal className="w-8 h-8 stroke-1 text-text-muted/40 mb-2" />
                <p className="text-[11px]">暂无 ReAct 轨迹</p>
                <p className="text-[10px] text-text-muted/70 mt-1">智能体触发工具调用时将在此处实时捕获</p>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
};
