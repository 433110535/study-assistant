export interface ToolCallInfo {
  id: string;
  name: string;
  args: Record<string, any>;
  result?: string;
  status: 'calling' | 'done' | 'error';
  iteration?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  toolCalls?: ToolCallInfo[];
  status: 'streaming' | 'completed' | 'error';
  imagePreview?: string;
  timestamp?: string;
  isHistorical?: boolean; // 区分是否为缺少 ReAct 遥测的持久化历史记录
}

export interface SessionItem {
  session_id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
}
