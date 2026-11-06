import { useState, useCallback, useRef } from 'react';
import { ChatMessage, ToolCallInfo } from '@/types/chat';

export function useChatStream(initialSessionId: string = '') {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (prompt: string, imagePreview?: string, targetSessionId?: string) => {
      const cleanPrompt = prompt.trim();
      if (!cleanPrompt && !imagePreview) return;

      const userMsgId = `usr_${Date.now()}`;
      const assistantMsgId = `ast_${Date.now()}`;

      const userMsg: ChatMessage = {
        id: userMsgId,
        role: 'user',
        content: cleanPrompt,
        status: 'completed',
        imagePreview,
        timestamp: new Date().toISOString(),
      };

      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        thinking: '',
        toolCalls: [],
        status: 'streaming',
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const sid = targetSessionId || initialSessionId;
        const response = await fetch('/v1/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: sid || undefined,
            message: cleanPrompt,
          }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const errDetail = await response.text().catch(() => response.statusText);
          throw new Error(`SSE Stream Error [${response.status}]: ${errDetail}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        const iterationTracker = { current: 0 };
        const answerChunkTracker = { received: false };

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          // 师父指示 1：stream: true 严防 UTF-8 多字节字符截断乱码
          buffer += decoder.decode(value, { stream: true });

          // 师父指示 2：兼容 Windows \r\n\r\n 换行符
          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() ?? '';

          for (const block of blocks) {
            const trimmedBlock = block.trim();
            if (!trimmedBlock) continue;

            const lines = trimmedBlock.split(/\r?\n/);
            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed.startsWith('data:')) continue;

              const jsonStr = trimmed.replace(/^data:\s*/, '').trim();
              if (jsonStr === '[DONE]') {
                break;
              }

              try {
                const event = JSON.parse(jsonStr);
                const eventType = (event.event_type || event.type || '').toString().toLowerCase();
                const content = event.content || event.text || '';
                const toolName = event.tool_name || event.name || '';
                const toolArgs = event.tool_args || event.args || {};
                const toolResult = event.tool_result || event.result || '';
                const currentIteration = Number(event.iteration || 0);

                setMessages((prev) =>
                  prev.map((msg) => {
                    if (msg.id !== assistantMsgId) return msg;

                    if (eventType === 'thinking') {
                      let thinkingPrefix = '';
                      // 师父指示 3：ReAct 多轮思考按 iteration 分割视觉段落
                      if (currentIteration > 1 && currentIteration !== iterationTracker.current) {
                        thinkingPrefix = `\n--- [第 ${currentIteration} 轮推理] ---\n`;
                        iterationTracker.current = currentIteration;
                      }

                      return {
                        ...msg,
                        thinking: (msg.thinking || '') + thinkingPrefix + (content ? `${content}\n` : ''),
                      };
                    }

                    if (eventType === 'tool_call') {
                      const newToolCall: ToolCallInfo = {
                        id: `tc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
                        name: toolName || 'unknown_tool',
                        args: toolArgs,
                        status: 'calling',
                        iteration: currentIteration,
                      };
                      return {
                        ...msg,
                        toolCalls: [...(msg.toolCalls || []), newToolCall],
                      };
                    }

                    if (eventType === 'tool_result') {
                      const calls = [...(msg.toolCalls || [])];
                      // 师父指示 4：同名工具二次调用冲突处理，优先寻找最后一个处于 calling 的匹配工具
                      for (let i = calls.length - 1; i >= 0; i--) {
                        if (
                          calls[i].status === 'calling' &&
                          (!toolName || calls[i].name === toolName)
                        ) {
                          calls[i] = {
                            ...calls[i],
                            result: typeof toolResult === 'string' ? toolResult : JSON.stringify(toolResult),
                            status: 'done',
                          };
                          break;
                        }
                      }
                      return {
                        ...msg,
                        toolCalls: calls,
                      };
                    }

                    if (eventType === 'answer_chunk') {
                      answerChunkTracker.received = true;
                      return {
                        ...msg,
                        content: msg.content + content,
                      };
                    }

                    if (eventType === 'final_answer') {
                      // 师父指示 5：去重防御，若已累加过 answer_chunk 则不重复覆盖或双倍拼接
                      return {
                        ...msg,
                        content: answerChunkTracker.received ? msg.content : (msg.content || content),
                        status: 'completed',
                      };
                    }

                    if (eventType === 'error') {
                      return {
                        ...msg,
                        status: 'error',
                        content: msg.content + `\n[系统执行异常: ${content || event.message || '未知错误'}]`,
                      };
                    }

                    return msg;
                  })
                );
              } catch (parseErr) {
                console.warn('Failed to parse SSE JSON block:', jsonStr, parseErr);
              }
            }
          }
        }

        // 流结束正常收尾
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId && msg.status === 'streaming'
              ? { ...msg, status: 'completed' }
              : msg
          )
        );
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.error('Chat stream failed:', err);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    status: 'error',
                    content: msg.content + `\n[请求失败: ${err.message || '连接异常'}]`,
                  }
                : msg
            )
          );
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [initialSessionId]
  );

  // 师父指示 6：切会话必断流
  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  }, []);

  return {
    messages,
    setMessages,
    isStreaming,
    sendMessage,
    stopStream,
  };
}
