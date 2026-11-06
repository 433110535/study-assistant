import React, { useState, useRef } from 'react';
import { Send, Image as ImageIcon, X, Loader2, Square } from 'lucide-react';

interface ChatInputBoxProps {
  onSendMessage: (prompt: string, imagePreview?: string) => void;
  onStopStream: () => void;
  disabled: boolean;
  isStreaming: boolean;
}

export const ChatInputBox: React.FC<ChatInputBoxProps> = ({
  onSendMessage,
  onStopStream,
  disabled,
  isStreaming,
}) => {
  const [input, setInput] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [ocrNotice, setOcrNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 统一的图片上传与 OCR 识别函数
  const processImageFile = async (file: File) => {
    if (!file.type.startsWith('image/')) return;

    const reader = new FileReader();
    reader.onload = async () => {
      const base64Str = reader.result as string;
      setImagePreview(base64Str);

      setOcrLoading(true);
      setOcrNotice('[OCR_SCANNING...] 正在调用 DashScope VL 模型解析题目与公式...');

      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('focus', '全部');

        const res = await fetch('/v1/vision/ocr', {
          method: 'POST',
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          if (data.text) {
            setInput((prev) => (prev.trim() ? `${prev}\n\n[题目内容识别]:\n${data.text}` : data.text));
            setOcrNotice(`${data.model || 'qwen-vl-max'} · ${data.elapsed_ms || 0}ms · 识别完成，可手动修改`);
          }
        } else {
          const errDetail = await res.text();
          setOcrNotice(`OCR 识别异常: ${errDetail || res.statusText}`);
        }
      } catch (err: any) {
        console.error('OCR failed:', err);
        setOcrNotice(`OCR 调用失败: ${err.message || '网络连接异常'}`);
      } finally {
        setOcrLoading(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processImageFile(file);
    }
  };

  // 师父指示：支持剪贴板直接粘贴截图 (onPaste)
  const handlePaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();
          await processImageFile(file);
          break;
        }
      }
    }
  };

  const handleSend = () => {
    // 师父指示：OCR 扫描中禁止发送
    if (ocrLoading || (!input.trim() && !imagePreview) || disabled) return;
    onSendMessage(input, imagePreview || undefined);
    setInput('');
    setImagePreview(null);
    setOcrNotice(null);
  };

  return (
    <div className="bg-surface border-t border-border p-3 md:p-4 shrink-0 font-mono">
      {/* 师父指示：图片 OCR 预览与 ClickHouse 风格状态条 */}
      {imagePreview && (
        <div className="mb-3 flex items-center justify-between bg-surface-2 border border-border p-2.5 rounded-sm">
          <div className="flex items-center gap-3 min-w-0">
            <img
              src={imagePreview}
              alt="OCR Preview"
              className="w-12 h-12 object-cover rounded-xs border border-border shrink-0 bg-[#000]"
            />
            <div className="text-xs min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-accent uppercase font-bold text-[11px] tracking-wider">
                  OCR ATTACHMENT
                </span>
                {ocrLoading && (
                  <span className="flex items-center gap-1 text-[10px] text-accent px-1.5 py-0.2 bg-accent/10 border border-accent/40 rounded-xs">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    OCR_SCANNING...
                  </span>
                )}
              </div>
              <span className="text-text-secondary block text-[11px] mt-0.5 truncate">
                {ocrNotice || '已提取题目文字并回填至下方输入框'}
              </span>
            </div>
          </div>
          <button
            onClick={() => {
              setImagePreview(null);
              setOcrNotice(null);
            }}
            disabled={ocrLoading}
            className="p-1.5 text-text-muted hover:text-text-primary bg-surface rounded-xs border border-border hover:border-danger transition-colors shrink-0 disabled:opacity-50"
            title="移除图片附件"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="flex items-end gap-2">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
        />

        {/* 📷 OCR 按钮 */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={ocrLoading || disabled || isStreaming}
          className="p-3 bg-surface-2 border border-border rounded-sm text-text-secondary hover:text-accent hover:border-accent transition-colors disabled:opacity-40 shrink-0"
          title="上传作业/试卷照片触发 OCR 识别 (亦支持在输入框内 Ctrl+V 直接粘贴截图)"
        >
          {ocrLoading ? (
            <Loader2 className="w-4 h-4 animate-spin text-accent" />
          ) : (
            <ImageIcon className="w-4 h-4" />
          )}
        </button>

        {/* 多行输入框 (带 onPaste 监听) */}
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={disabled && !isStreaming}
          placeholder="输入学习疑问、概念探讨，或直接 Ctrl+V 粘贴错题截图 (Ctrl+Enter 发送)..."
          rows={2}
          className="flex-1 bg-surface-2 border border-border rounded-sm p-3 text-xs text-text-primary focus:outline-none focus:border-accent resize-none placeholder:text-text-muted leading-relaxed"
        />

        {/* 发送 / 中断 按钮 */}
        {isStreaming ? (
          <button
            onClick={onStopStream}
            className="px-4 py-3 bg-danger/20 border border-danger/50 text-danger hover:bg-danger hover:text-bg font-bold text-xs uppercase tracking-label rounded-sm flex items-center gap-1.5 transition-colors shrink-0"
            title="中断流式生成"
          >
            <Square className="w-4 h-4 fill-current" />
            <span className="hidden sm:inline">停止</span>
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || ocrLoading || (!input.trim() && !imagePreview)}
            className="px-4 py-3 bg-accent active:bg-accent-active text-bg font-bold text-xs uppercase tracking-label rounded-sm flex items-center gap-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            title={ocrLoading ? '正在识别图片中...' : '发送消息'}
          >
            <Send className="w-4 h-4 fill-current" />
            <span className="hidden sm:inline">发送</span>
          </button>
        )}
      </div>
    </div>
  );
};
