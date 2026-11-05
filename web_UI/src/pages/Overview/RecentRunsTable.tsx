import React from 'react';
import { RecentRun } from '@/types/dashboard';
import { Activity, Clock, Zap } from 'lucide-react';

interface RecentRunsTableProps {
  runs: RecentRun[];
}

export const RecentRunsTable: React.FC<RecentRunsTableProps> = ({ runs }) => {
  return (
    <div className="p-4 md:p-6 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)]">
      {/* 标题 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#FAFF69]" />
          <h3 className="font-mono text-xs font-black tracking-label text-white uppercase">
            RECENT RUNS // 最近调用流水
          </h3>
        </div>
        <span className="text-[10px] font-mono text-[#71717A] uppercase tracking-label">
          TOP 5 EXECUTIONS
        </span>
      </div>

      {/* 表格容器 */}
      {runs.length === 0 ? (
        <div className="py-12 border border-dashed border-[rgba(65,65,65,0.8)] rounded-sm text-center">
          <Activity className="w-8 h-8 text-[#71717A] mx-auto mb-2 opacity-50" />
          <p className="font-mono text-xs text-[#A1A1AA] uppercase tracking-label">
            NO RECENT ENGINE RUNS RECORDED
          </p>
          <p className="text-xs text-[#71717A] mt-1">
            在对话或代码沙箱中发起执行后将实时沉淀流水
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto border border-[rgba(65,65,65,0.8)] rounded-sm">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-black border-b border-[rgba(65,65,65,0.8)] text-[#A1A1AA] uppercase tracking-label text-[10px]">
                <th className="py-2.5 px-3">RUN ID</th>
                <th className="py-2.5 px-3">PROMPT PREVIEW</th>
                <th className="py-2.5 px-3">STATUS</th>
                <th className="py-2.5 px-3 text-right">LATENCY</th>
                <th className="py-2.5 px-3 text-right">TIMESTAMP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[rgba(65,65,65,0.5)]">
              {runs.map((run) => {
                const isSuccess = run.status.toLowerCase() === 'success' || run.status.toLowerCase() === 'completed';
                const isError = run.status.toLowerCase().includes('error') || run.status.toLowerCase().includes('fail');

                return (
                  <tr
                    key={run.id}
                    className="hover:bg-[#1a1a1a] transition-colors"
                  >
                    {/* ID */}
                    <td className="py-2.5 px-3 font-bold text-white whitespace-nowrap">
                      {run.id.slice(0, 8)}
                    </td>

                    {/* 内容预览 */}
                    <td className="py-2.5 px-3 text-[#A1A1AA] max-w-[240px] truncate" title={run.prompt_preview}>
                      {run.prompt_preview || '（空指令）'}
                    </td>

                    {/* 状态 */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-label ${
                          isSuccess
                            ? 'bg-[#166534] text-white'
                            : isError
                            ? 'bg-[#EF4444]/20 border border-[#EF4444]/50 text-[#EF4444]'
                            : 'bg-[#141414] border border-[rgba(65,65,65,0.8)] text-[#FAFF69]'
                        }`}
                      >
                        {isSuccess && <Zap className="w-2.5 h-2.5" />}
                        {run.status}
                      </span>
                    </td>

                    {/* 耗时 */}
                    <td className="py-2.5 px-3 text-right whitespace-nowrap text-[#A1A1AA]">
                      <span className="inline-flex items-center gap-1 justify-end">
                        <Clock className="w-3 h-3 text-[#71717A]" />
                        {run.latency_ms ? `${run.latency_ms}ms` : '-'}
                      </span>
                    </td>

                    {/* 时间 */}
                    <td className="py-2.5 px-3 text-right whitespace-nowrap text-[#71717A]">
                      {run.created_at ? new Date(run.created_at).toLocaleTimeString() : '-'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
