import React from 'react';
import { Plus, MessageSquare, Trash2, Clock, Terminal } from 'lucide-react';
import { SessionItem } from '@/types/chat';

interface SessionSidebarProps {
  sessions: SessionItem[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession?: (id: string) => void;
  isLoading?: boolean;
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isLoading = false,
}) => {
  return (
    <aside className="w-64 border-r border-border bg-surface flex flex-col h-full shrink-0 font-mono text-xs">
      {/* 顶部新建按钮 */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-surface-2 hover:bg-surface border border-border hover:border-accent text-text-primary hover:text-accent rounded-sm tracking-label uppercase font-bold transition-colors"
        >
          <Plus className="w-4 h-4 text-accent" />
          <span>新建会话</span>
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {isLoading ? (
          <div className="p-4 text-center text-text-muted">加载会话中...</div>
        ) : sessions.length === 0 ? (
          <div className="p-6 text-center text-text-muted flex flex-col items-center gap-2">
            <MessageSquare className="w-6 h-6 text-text-muted/40 stroke-1" />
            <span>暂无历史会话</span>
          </div>
        ) : (
          sessions.map((sess) => {
            const isActive = sess.session_id === activeSessionId;
            return (
              <div
                key={sess.session_id}
                onClick={() => onSelectSession(sess.session_id)}
                className={`group relative flex items-center justify-between p-2.5 rounded-sm cursor-pointer transition-colors ${
                  isActive
                    ? 'bg-surface-2 text-text-primary border-l-2 border-accent pl-2'
                    : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 pr-2">
                  <Terminal
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isActive ? 'text-accent' : 'text-text-muted group-hover:text-text-secondary'
                    }`}
                  />
                  <div className="truncate text-xs font-sans font-medium text-text-primary">
                    {sess.title || '无标题会话'}
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {sess.message_count !== undefined && (
                    <span className="text-[10px] text-text-muted px-1 py-0.5 bg-surface rounded-xs border border-border">
                      {sess.message_count}
                    </span>
                  )}
                  {onDeleteSession && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(sess.session_id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-text-muted hover:text-danger rounded-xs transition-opacity"
                      title="删除会话"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 底部信息条 */}
      <div className="p-3 border-t border-border bg-[#050505] text-[11px] text-text-muted flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-text-muted" />
          <span>本地单机存储</span>
        </div>
        <span className="text-accent uppercase text-[10px] font-bold">SQLITE WAL</span>
      </div>
    </aside>
  );
};
