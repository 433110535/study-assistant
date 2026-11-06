import React, { useEffect, useRef } from 'react';
import { Bot, User, Activity, Clock } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolCallCard } from './ToolCallCard';

interface ChatMessageAreaProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onOpenInspector: (msg: ChatMessage) => void;
  activeInspectorMsgId?: string | null;
}

export const ChatMessageArea: React.FC<ChatMessageAreaProps> = ({
  messages,
  isStreaming,
  onOpenInspector,
  activeInspectorMsgId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef<boolean>(true);

  // 师父指示：智能吸底与反劫持，监听用户向上滚动
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    isNearBottomRef.current = scrollHeight - scrollTop - clientHeight <= 80;
  };

  useEffect(() => {
    if (!containerRef.current) return;
    if (isNearBottomRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-bg font-mono select-none">
        <div className="w-12 h-12 rounded-sm bg-surface-2 border border-border flex items-center justify-center mb-4">
          <Bot className="w-6 h-6 text-accent" />
        </div>
        <h2 className="text-xl font-bold tracking-tight text-text-primary uppercase mb-2">
          JESSE · 智能答疑会话终端
        </h2>
        <p className="text-xs text-text-muted max-w-md leading-relaxed font-sans">
          基于 ReAct 循环推理引擎。支持拍照识题 OCR、教材 RAG 检索、代码沙箱执行诊断与到期主动复习排程。
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-bg"
    >
      {messages.map((msg) => {
        const isUser = msg.role === 'user';
        const hasTools = msg.toolCalls && msg.toolCalls.length > 0;
        const isSelectedForInspect = activeInspectorMsgId === msg.id;

        return (
          <div
            key={msg.id}
            className={`flex gap-3 md:gap-4 max-w-4xl mx-auto ${
              isUser ? 'justify-end' : 'justify-start'
            }`}
          >
            {/* Assistant 头像 */}
            {!isUser && (
              <div className="w-8 h-8 rounded-xs bg-surface-2 border border-border flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-accent" />
              </div>
            )}

            <div className={`space-y-2 min-w-0 ${isUser ? 'max-w-[85%] md:max-w-[75%]' : 'flex-1'}`}>
              {/* 消息主体卡片 */}
              <div
                className={`p-4 rounded-sm text-xs md:text-sm leading-relaxed font-sans ${
                  isUser
                    ? 'bg-surface border border-border text-text-primary rounded-tr-none'
                    : `bg-surface-2 border ${
                        isSelectedForInspect ? 'border-accent' : 'border-border'
                      } text-text-primary border-l-2 border-l-accent`
                }`}
              >
                {/* 针对 Assistant 消息，若有思考过程则在卡片顶部折叠展示 */}
                {!isUser && msg.thinking && (
                  <ThinkingBlock thinking={msg.thinking} isStreaming={msg.status === 'streaming'} />
                )}

                {/* 针对 Assistant 消息，若有工具调用则内联展示卡片 */}
                {!isUser && hasTools && (
                  <div className="mb-3 space-y-1.5">
                    <div className="flex items-center justify-between font-mono text-[11px] text-text-muted pb-1 border-b border-border/40">
                      <span className="uppercase text-accent font-bold">
                        TOOLS EXECUTED ({msg.toolCalls?.length})
                      </span>
                      <button
                        onClick={() => onOpenInspector(msg)}
                        className="flex items-center gap-1 text-text-secondary hover:text-accent transition-colors"
                      >
                        <Activity className="w-3 h-3 text-accent" />
                        <span>聚焦轨迹</span>
                      </button>
                    </div>
                    {msg.toolCalls?.map((tc) => (
                      <ToolCallCard key={tc.id} toolCall={tc} />
                    ))}
                  </div>
                )}

                {/* 图片附件展示 */}
                {msg.imagePreview && (
                  <div className="mb-3">
                    <img
                      src={msg.imagePreview}
                      alt="Uploaded"
                      className="max-h-60 rounded-xs border border-border object-contain bg-[#050505]"
                    />
                  </div>
                )}

                {/* 文本内容 */}
                <div className="whitespace-pre-wrap break-words leading-relaxed font-sans">
                  {msg.content}
                  {msg.status === 'streaming' && (
                    <span className="inline-block w-2 h-4 bg-accent ml-1 animate-pulse align-middle" />
                  )}
                </div>
              </div>

              {/* 底部元信息与轨迹聚焦标签 */}
              <div
                className={`flex items-center gap-2 text-[10px] font-mono text-text-muted ${
                  isUser ? 'justify-end' : 'justify-start'
                }`}
              >
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-text-muted/60" />
                  <span>
                    {msg.timestamp
                      ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : ''}
                  </span>
                </div>

                {/* 师父指示：ClickHouse 风格硬朗标签 [TRACE: N STEPS] */}
                {!isUser && (hasTools || msg.thinking) && (
                  <button
                    onClick={() => onOpenInspector(msg)}
                    className="px-1.5 py-0.5 bg-surface border border-border hover:border-accent text-text-secondary hover:text-accent rounded-xs transition-colors font-bold uppercase tracking-wider"
                  >
                    [TRACE: {msg.toolCalls?.length || (msg.thinking ? 1 : 0)} STEPS]
                  </button>
                )}
              </div>
            </div>

            {/* User 头像 */}
            {isUser && (
              <div className="w-8 h-8 rounded-xs bg-surface border border-border flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-text-secondary" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
