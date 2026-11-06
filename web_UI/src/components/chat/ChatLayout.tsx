import React, { useState } from 'react';
import { PanelLeft, Activity } from 'lucide-react';
import { SessionSidebar } from './SessionSidebar';
import { ChatMessageArea } from './ChatMessageArea';
import { ChatInputBox } from './ChatInputBox';
import { ReActInspector } from './ReActInspector';
import { ChatMessage, SessionItem } from '@/types/chat';

interface ChatLayoutProps {
  sessions: SessionItem[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession?: (id: string) => void;
  messages: ChatMessage[];
  isStreaming: boolean;
  onSendMessage: (prompt: string, imagePreview?: string) => void;
  onStopStream: () => void;
  isLoadingSessions?: boolean;
}

export const ChatLayout: React.FC<ChatLayoutProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  messages,
  isStreaming,
  onSendMessage,
  onStopStream,
  isLoadingSessions = false,
}) => {
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightInspector, setShowRightInspector] = useState(true); // 桌面默认打开 320px 轨迹面板
  const [inspectedMessageId, setInspectedMessageId] = useState<string | null>(null);

  // 师父指示：流式传输中自动聚焦当前 Assistant 消息；空闲时回看用户指定消息或最新消息
  const streamingAssistantMessage = isStreaming
    ? [...messages].reverse().find((m) => m.role === 'assistant' && m.status === 'streaming')
    : null;

  const currentInspectedMessage =
    streamingAssistantMessage ||
    (inspectedMessageId ? messages.find((m) => m.id === inspectedMessageId) : null) ||
    [...messages].reverse().find((m) => m.role === 'assistant') ||
    null;

  const handleOpenInspector = (msg: ChatMessage) => {
    setInspectedMessageId(msg.id);
    setShowRightInspector(true);
  };

  const activeSession = sessions.find((s) => s.session_id === activeSessionId);

  return (
    <div className="flex-1 flex overflow-hidden bg-bg relative h-full">
      {/* 左侧会话侧栏 */}
      {showLeftSidebar && (
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={onSelectSession}
          onNewSession={onNewSession}
          onDeleteSession={onDeleteSession}
          isLoading={isLoadingSessions}
        />
      )}

      {/* 中间主视口 */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* 中间顶栏工具条 */}
        <div className="h-12 px-4 border-b border-border bg-surface flex items-center justify-between shrink-0 font-mono text-xs">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className="p-1.5 text-text-secondary hover:text-text-primary rounded-xs hover:bg-surface-2 transition-colors"
              title="切换会话列表"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            <div className="truncate font-bold text-text-primary text-xs">
              {activeSession?.title || 'JESSE 交互答疑工作区'}
            </div>
            {isStreaming && (
              <span className="px-2 py-0.5 bg-accent/10 border border-accent/40 text-accent text-[10px] rounded-xs font-bold uppercase animate-pulse">
                STREAMING ACTIVE
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRightInspector(!showRightInspector)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border transition-colors text-xs font-mono uppercase tracking-label ${
                showRightInspector
                  ? 'bg-accent text-bg border-accent font-bold'
                  : 'bg-surface-2 border-border text-text-secondary hover:text-text-primary'
              }`}
              title="切换 ReAct 轨迹面板"
            >
              <Activity className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">TRAJECTORY</span>
            </button>
          </div>
        </div>

        {/* 消息主流视口 */}
        <ChatMessageArea
          messages={messages}
          isStreaming={isStreaming}
          onOpenInspector={handleOpenInspector}
          activeInspectorMsgId={currentInspectedMessage?.id}
        />

        {/* 底部输入框 */}
        <ChatInputBox
          onSendMessage={onSendMessage}
          onStopStream={onStopStream}
          disabled={false}
          isStreaming={isStreaming}
        />
      </main>

      {/* 右侧 ReAct Inspector 面板 */}
      <ReActInspector
        currentMessage={currentInspectedMessage}
        isOpen={showRightInspector}
        onClose={() => setShowRightInspector(false)}
        isStreaming={isStreaming}
      />
    </div>
  );
};
