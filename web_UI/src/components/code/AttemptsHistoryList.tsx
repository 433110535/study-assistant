import React, { useState, useEffect, useCallback } from 'react';
import { fetchCodeAttempts } from '@/lib/api-client';
import { CodeAttempt } from '@/types/code';
import { History, RotateCcw, ArrowUpLeft } from 'lucide-react';

interface AttemptsHistoryListProps {
  threadId?: string;
  onRestoreCode: (code: string, tests?: string) => void;
  refreshKey: number;
}

export const AttemptsHistoryList: React.FC<AttemptsHistoryListProps> = ({
  threadId,
  onRestoreCode,
  refreshKey,
}) => {
  const [attempts, setAttempts] = useState<CodeAttempt[]>([]);
  const [loading, setLoading] = useState(false);

  const loadAttempts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchCodeAttempts(threadId, 30);
      setAttempts(res.attempts || []);
    } catch (err: any) {
      console.error('Failed to load code attempts', err);
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    let active = true;
    fetchCodeAttempts(threadId, 30)
      .then((res) => {
        if (active) {
          setAttempts(res.attempts || []);
        }
      })
      .catch((err) => {
        if (active) console.error('Failed to load code attempts', err);
      });
    return () => {
      active = false;
    };
  }, [threadId, refreshKey]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'passed':
        return (
          <span className="px-1.5 py-0.5 border border-[#4ADE80] bg-[#4ADE80]/10 text-[#4ADE80] text-[10px] font-bold">
            [PASS]
          </span>
        );
      case 'timeout':
        return (
          <span className="px-1.5 py-0.5 border border-[#FAFF69] bg-[#FAFF69]/10 text-[#FAFF69] text-[10px] font-bold">
            [TLE]
          </span>
        );
      case 'memory':
      case 'memory_limit':
        return (
          <span className="px-1.5 py-0.5 border border-red-500 bg-red-950/20 text-red-400 text-[10px] font-bold">
            [MLE]
          </span>
        );
      case 'rejected':
      case 'security_violation':
        return (
          <span className="px-1.5 py-0.5 border border-red-500 bg-red-950/20 text-red-400 text-[10px] font-bold">
            [SECURITY]
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 border border-red-500/60 bg-red-950/20 text-red-400 text-[10px] font-bold">
            [FAIL]
          </span>
        );
    }
  };

  return (
    <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] font-mono text-sm flex flex-col">
      {/* Header */}
      <div className="p-2.5 border-b border-[rgba(65,65,65,0.8)] bg-black flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-[#FAFF69]" />
          <span className="text-xs text-white font-bold tracking-wider">
            EXECUTION_ATTEMPTS_HISTORY ({attempts.length})
          </span>
        </div>
        <button
          type="button"
          onClick={loadAttempts}
          className="p-1 border border-[rgba(65,65,65,0.8)] text-neutral-400 hover:text-white"
          title="Refresh History"
        >
          <RotateCcw className="w-3 h-3" />
        </button>
      </div>

      {/* List */}
      <div className="p-2 bg-black min-h-[140px] max-h-[260px] overflow-y-auto divide-y divide-[rgba(65,65,65,0.8)]">
        {loading ? (
          <div className="p-6 text-center text-xs text-neutral-500">
            [FETCHING_ATTEMPTS_FROM_DB...]
          </div>
        ) : attempts.length === 0 ? (
          <div className="p-6 text-center text-xs text-neutral-600">
            暂无历史执行记录。运行代码后将自动归档。
          </div>
        ) : (
          [...attempts].reverse().map((att) => (
            <div
              key={att.id}
              className="p-2.5 hover:bg-white/[0.02] transition-colors flex items-center justify-between gap-2"
            >
              <div className="flex items-center space-x-2 min-w-0">
                <span className="text-xs text-neutral-500 font-bold">
                  #{att.seq}
                </span>
                {getStatusBadge(att.status)}
                <div className="min-w-0">
                  <div className="text-xs text-neutral-200 truncate">
                    {att.exception_type ? `${att.exception_type}: ` : ''}
                    {att.exception_message || att.stdout_preview || 'Passed with no errors'}
                  </div>
                  <div className="text-[10px] text-neutral-500">
                    {att.created_at ? new Date(att.created_at).toLocaleTimeString() : ''}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => onRestoreCode(att.code, att.tests || '')}
                className="px-2 py-0.5 border border-neutral-700 hover:border-[#FAFF69] hover:text-[#FAFF69] text-neutral-300 text-[10px] font-bold flex items-center space-x-1 cursor-pointer flex-shrink-0"
                title="回滚恢复此版本代码"
              >
                <ArrowUpLeft className="w-3 h-3" />
                <span>RESTORE</span>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
