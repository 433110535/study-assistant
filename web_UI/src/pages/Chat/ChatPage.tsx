import React, { useState, useEffect, useCallback } from 'react';
import { ChatLayout } from '@/components/chat/ChatLayout';
import { useChatStream } from '@/hooks/useChatStream';
import { SessionItem, ChatMessage } from '@/types/chat';

export const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(true);

  const { messages, setMessages, isStreaming, sendMessage, stopStream } = useChatStream(activeSessionId);

  // 拉取历史会话列表
  const fetchSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const res = await fetch('/v1/sessions?user_id=student&limit=50');
      if (res.ok) {
        const data = await res.json();
        const rawSessions = Array.isArray(data.sessions) ? data.sessions : [];
        const formatted: SessionItem[] = rawSessions.map((s: any) => ({
          session_id: s.id || s.session_id,
          title: s.title || '学习会话',
          created_at: s.created_at,
          updated_at: s.updated_at,
          message_count: s.message_count || 0,
        }));
        setSessions(formatted);
        if (formatted.length > 0 && !activeSessionId) {
          setActiveSessionId(formatted[0].session_id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [activeSessionId]);

  useEffect(() => {
    void fetchSessions();
  }, [fetchSessions]);

  // 加载选定会话的历史消息
  const loadSessionMessages = useCallback(
    async (sid: string) => {
      if (!sid) {
        setMessages([]);
        return;
      }
      try {
        const res = await fetch(`/v1/sessions/${sid}/messages`);
        if (res.ok) {
          const data = await res.json();
          const rawMsgs = Array.isArray(data.messages) ? data.messages : [];
          const formatted: ChatMessage[] = rawMsgs.map((m: any, idx: number) => ({
            id: `hist_${sid}_${idx}_${m.created_at}`,
            role: m.role === 'user' ? 'user' : 'assistant',
            content: m.content || '',
            status: 'completed',
            isHistorical: true, // 标记为历史持久化消息
            timestamp: m.created_at,
          }));
          setMessages(formatted);
        }
      } catch (err) {
        console.error('Failed to load session messages:', err);
      }
    },
    [setMessages]
  );

  // 师父指示：切会话必断流，且加载对应历史
  const handleSelectSession = (sid: string) => {
    if (sid === activeSessionId) return;
    if (isStreaming) {
      stopStream();
    }
    setActiveSessionId(sid);
    loadSessionMessages(sid);
  };

  // 新建空会话
  const handleNewSession = async () => {
    if (isStreaming) {
      stopStream();
    }
    try {
      const res = await fetch('/v1/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `新会话 ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const newSid = data.session_id;
        const newSess: SessionItem = {
          session_id: newSid,
          title: `新会话 ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
          created_at: new Date().toISOString(),
          message_count: 0,
        };
        setSessions((prev) => [newSess, ...prev]);
        setActiveSessionId(newSid);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  // 师父指示：无会话状态下的懒创建（Lazy Session Creation）
  const handleSendMessage = async (prompt: string, imagePreview?: string) => {
    let currentSid = activeSessionId;

    if (!currentSid) {
      try {
        const shortTitle = prompt.trim().slice(0, 16) || '图片识题问答';
        const res = await fetch('/v1/sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: shortTitle }),
        });
        if (res.ok) {
          const data = await res.json();
          currentSid = data.session_id;
          const newSess: SessionItem = {
            session_id: currentSid,
            title: shortTitle,
            created_at: new Date().toISOString(),
            message_count: 1,
          };
          setSessions((prev) => [newSess, ...prev]);
          setActiveSessionId(currentSid);
        }
      } catch (err) {
        console.error('Lazy session creation failed:', err);
      }
    }

    await sendMessage(prompt, imagePreview, currentSid);

    // 发送完成后静默刷新一次会话列表以更新 message_count
    setTimeout(() => {
      fetchSessions();
    }, 1000);
  };

  return (
    <div className="flex-1 flex overflow-hidden h-full">
      <ChatLayout
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        messages={messages}
        isStreaming={isStreaming}
        onSendMessage={handleSendMessage}
        onStopStream={stopStream}
        isLoadingSessions={isLoadingSessions}
      />
    </div>
  );
};
