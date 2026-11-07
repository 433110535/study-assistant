import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchTraces,
  fetchTraceDetail,
  fetchEvalRuns,
  fetchEvalCompare,
  fetchDatasets,
} from '@/lib/api-client';
import { TraceItem, ToolCallItem, EvalRunItem } from '@/types/ops';
import {
  Activity,
  Layers,
  Database,
  ChevronRight,
  GitCompare,
  X,
  Filter,
} from 'lucide-react';

export const OpsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'traces' | 'eval' | 'datasets'>('traces');

  // Traces State
  const [tracePage, setTracePage] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  // Eval Compare State
  const [baseRunId, setBaseRunId] = useState('');
  const [targetRunId, setTargetRunId] = useState('');
  const [compareTriggered, setCompareTriggered] = useState(false);

  // Queries
  const { data: tracesData, isLoading: tracesLoading } = useQuery({
    queryKey: ['ops-traces', tracePage, statusFilter],
    queryFn: () => fetchTraces(20, tracePage * 20, statusFilter),
  });

  const { data: traceDetail, isLoading: traceDetailLoading } = useQuery({
    queryKey: ['ops-trace-detail', selectedTraceId],
    queryFn: () => (selectedTraceId ? fetchTraceDetail(selectedTraceId) : null),
    enabled: Boolean(selectedTraceId),
  });

  const { data: evalRuns = [], isLoading: evalLoading } = useQuery({
    queryKey: ['ops-eval-runs'],
    queryFn: () => fetchEvalRuns(50),
  });

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ['ops-eval-compare', baseRunId, targetRunId],
    queryFn: () => (baseRunId && targetRunId ? fetchEvalCompare(baseRunId, targetRunId) : null),
    enabled: Boolean(compareTriggered && baseRunId && targetRunId),
  });

  const { data: datasetsData, isLoading: datasetsLoading } = useQuery({
    queryKey: ['ops-datasets'],
    queryFn: fetchDatasets,
  });

  return (
    <div className="space-y-6">
      {/* 顶部标题区 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[rgba(65,65,65,0.8)] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#FAFF69] text-black font-black uppercase tracking-wider">
              U7 PLATFORM
            </span>
            <span className="text-xs font-mono text-[#A0A0A0]">数据中台 · 评测底座 · 可观测性</span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-black tracking-tight text-white mt-1">
            OPS & EVALUATION
          </h1>
        </div>

        {/* 顶部 Tab 切换 */}
        <div className="flex items-center gap-1 bg-[#141414] p-1 rounded-sm border border-[rgba(65,65,65,0.8)]">
          <button
            onClick={() => setActiveTab('traces')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors ${
              activeTab === 'traces'
                ? 'bg-[#FAFF69] text-black'
                : 'text-[#A0A0A0] hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            链路追踪 TRACES
          </button>
          <button
            onClick={() => setActiveTab('eval')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors ${
              activeTab === 'eval'
                ? 'bg-[#FAFF69] text-black'
                : 'text-[#A0A0A0] hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            评测与对比 EVAL
          </button>
          <button
            onClick={() => setActiveTab('datasets')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors ${
              activeTab === 'datasets'
                ? 'bg-[#FAFF69] text-black'
                : 'text-[#A0A0A0] hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            评测集资产 DATASETS
          </button>
        </div>
      </div>

      {/* 选项卡 1：链路追踪 (Traces) */}
      {activeTab === 'traces' && (
        <div className="space-y-4">
          {/* 筛选过滤条 */}
          <div className="flex items-center justify-between gap-4 bg-[#141414] p-3 rounded-sm border border-[rgba(65,65,65,0.8)]">
            <div className="flex items-center gap-3">
              <Filter className="w-4 h-4 text-[#FAFF69]" />
              <span className="text-xs font-bold text-[#A0A0A0] uppercase tracking-wider">状态筛选:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setTracePage(0);
                }}
                className="bg-[#0A0A0A] text-xs text-white border border-[rgba(65,65,65,0.8)] rounded-sm px-2.5 py-1 focus:border-[#FAFF69] focus:outline-none"
              >
                <option value="">全部状态 (ALL)</option>
                <option value="ok">成功 (OK)</option>
                <option value="error">异常 (ERROR)</option>
                <option value="running">运行中 (RUNNING)</option>
              </select>
            </div>
            <div className="text-xs font-mono text-[#A0A0A0]">
              总共 <span className="text-[#FAFF69] font-bold">{tracesData?.total ?? 0}</span> 条运行记录
            </div>
          </div>

          {/* Traces 列表表格 */}
          <div className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] rounded-sm overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#141414] text-[#A0A0A0] uppercase border-b border-[rgba(65,65,65,0.8)]">
                <tr>
                  <th className="py-2.5 px-3">RUN / TRACE ID</th>
                  <th className="py-2.5 px-3">STATUS</th>
                  <th className="py-2.5 px-3">MODEL</th>
                  <th className="py-2.5 px-3">INPUT PREVIEW</th>
                  <th className="py-2.5 px-3">LATENCY</th>
                  <th className="py-2.5 px-3">COST</th>
                  <th className="py-2.5 px-3">TIME</th>
                  <th className="py-2.5 px-3 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(65,65,65,0.5)]">
                {tracesLoading ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-[#A0A0A0]">
                      加载中...
                    </td>
                  </tr>
                ) : !tracesData?.traces.length ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-[#A0A0A0]">
                      暂无 Trace 记录
                    </td>
                  </tr>
                ) : (
                  tracesData.traces.map((trace: TraceItem) => (
                    <tr
                      key={trace.id}
                      onClick={() => setSelectedTraceId(trace.id)}
                      className={`hover:bg-[#141414] cursor-pointer transition-colors ${
                        selectedTraceId === trace.id ? 'bg-[#141414] border-l-2 border-[#FAFF69]' : ''
                      }`}
                    >
                      <td className="py-2.5 px-3 text-white font-bold">
                        {trace.id.slice(0, 8)}...
                        {trace.trace_id && (
                          <span className="block text-[10px] text-[#A0A0A0]">
                            {trace.trace_id.slice(0, 8)}
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded-sm text-[10px] font-bold uppercase ${
                            trace.status === 'ok'
                              ? 'bg-[#166534] text-[#4ADE80]'
                              : trace.status === 'error'
                              ? 'bg-[#FF6B6B]/20 text-[#FF6B6B]'
                              : 'bg-[#FAFF69]/20 text-[#FAFF69]'
                          }`}
                        >
                          {trace.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-[#A0A0A0]">{trace.model || 'default'}</td>
                      <td className="py-2.5 px-3 text-white max-w-[240px] truncate">
                        {trace.user_input_preview || '-'}
                      </td>
                      <td className="py-2.5 px-3 text-[#A0A0A0]">
                        {trace.latency_ms ? `${trace.latency_ms}ms` : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-[#FAFF69]">
                        {trace.cost_yuan !== undefined && trace.cost_yuan !== null
                          ? `¥${Number(trace.cost_yuan).toFixed(4)}`
                          : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-[#71717A]">
                        {trace.created_at?.slice(0, 19).replace('T', ' ')}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button className="text-[#FAFF69] hover:underline flex items-center gap-0.5 ml-auto text-xs">
                          详情 <ChevronRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 分页控制 */}
          {tracesData && tracesData.total > 20 && (
            <div className="flex justify-between items-center text-xs font-mono text-[#A0A0A0] pt-2">
              <div>
                第 {tracePage + 1} 页 / 共 {Math.ceil(tracesData.total / 20)} 页
              </div>
              <div className="flex gap-2">
                <button
                  disabled={tracePage === 0}
                  onClick={() => setTracePage((p) => Math.max(0, p - 1))}
                  className="px-3 py-1 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm disabled:opacity-40 hover:text-white"
                >
                  上一页 PREV
                </button>
                <button
                  disabled={(tracePage + 1) * 20 >= tracesData.total}
                  onClick={() => setTracePage((p) => p + 1)}
                  className="px-3 py-1 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm disabled:opacity-40 hover:text-white"
                >
                  下一页 NEXT
                </button>
              </div>
            </div>
          )}

          {/* 详情抽屉 (Modal / Detail Panel) */}
          {selectedTraceId && (
            <div className="bg-[#141414] border border-[#FAFF69] rounded-sm p-4 mt-4 space-y-4">
              <div className="flex items-center justify-between border-b border-[rgba(65,65,65,0.8)] pb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#FAFF69]" />
                  <span className="text-sm font-bold text-white uppercase font-mono">
                    Trace 运行详情: {selectedTraceId}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedTraceId(null)}
                  className="text-[#A0A0A0] hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {traceDetailLoading ? (
                <div className="text-xs text-[#A0A0A0] py-4 font-mono">加载运行全链路中...</div>
              ) : !traceDetail ? (
                <div className="text-xs text-[#FF6B6B] font-mono">无法加载该 Trace 详情</div>
              ) : (
                <div className="space-y-4 font-mono text-xs">
                  {/* 元信息卡片 */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#0A0A0A] p-3 rounded-sm border border-[rgba(65,65,65,0.8)]">
                    <div>
                      <span className="text-[10px] text-[#A0A0A0] uppercase block">耗时 LATENCY</span>
                      <span className="text-white font-bold">{traceDetail.run.latency_ms ?? 0}ms</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-[#A0A0A0] uppercase block">迭代轮数 ITERATIONS</span>
                      <span className="text-white font-bold">{traceDetail.run.iterations} 轮</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-[#A0A0A0] uppercase block">TOKEN 用量 (IN/OUT)</span>
                      <span className="text-white font-bold">
                        {traceDetail.run.token_in ?? 0} / {traceDetail.run.token_out ?? 0}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-[#A0A0A0] uppercase block">估算费用 COST</span>
                      <span className="text-[#FAFF69] font-bold">
                        ¥{Number(traceDetail.run.cost_yuan ?? 0).toFixed(4)}
                      </span>
                    </div>
                  </div>

                  {/* 最终回答 */}
                  {traceDetail.run.final_answer && (
                    <div className="bg-[#0A0A0A] p-3 rounded-sm border border-[rgba(65,65,65,0.8)]">
                      <span className="text-[10px] text-[#A0A0A0] uppercase block mb-1">FINAL ANSWER</span>
                      <div className="text-white whitespace-pre-wrap">
                        {traceDetail.run.final_answer}
                      </div>
                    </div>
                  )}

                  {/* Tool Calls 瀑布流时序 */}
                  <div>
                    <span className="text-[10px] text-[#FAFF69] font-bold uppercase tracking-wider block mb-2">
                      工具调用瀑布流 (TOOL CALLS WATERFALL - {traceDetail.tool_calls.length} CALLS)
                    </span>
                    {!traceDetail.tool_calls.length ? (
                      <div className="text-[#A0A0A0] py-2 text-xs">本轮无外部工具调用</div>
                    ) : (
                      <div className="space-y-2">
                        {traceDetail.tool_calls.map((call: ToolCallItem, idx: number) => (
                          <div
                            key={call.id || idx}
                            className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] rounded-sm p-2.5 flex flex-col gap-1"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="w-4 h-4 rounded-full bg-[#141414] text-[10px] font-bold text-[#FAFF69] flex items-center justify-center border border-[rgba(65,65,65,0.8)]">
                                  {idx + 1}
                                </span>
                                <span className="font-bold text-white text-xs">{call.tool_name}</span>
                                <span
                                  className={`px-1 py-0.2 rounded-sm text-[10px] ${
                                    call.status === 'ok'
                                      ? 'text-[#4ADE80] bg-[#166534]'
                                      : 'text-[#FF6B6B] bg-[#FF6B6B]/20'
                                  }`}
                                >
                                  {call.status}
                                </span>
                              </div>
                              <span className="text-[#A0A0A0] text-[10px]">
                                {call.latency_ms ? `${call.latency_ms}ms` : ''}
                              </span>
                            </div>
                            {call.args_json && (
                              <div className="text-[11px] text-[#A0A0A0] bg-[#141414] p-1.5 rounded-sm overflow-x-auto">
                                <span className="text-[#71717A]">ARGS: </span>
                                {call.args_json}
                              </div>
                            )}
                            {call.result_preview && (
                              <div className="text-[11px] text-[#E4E4E7] bg-[#141414] p-1.5 rounded-sm overflow-x-auto">
                                <span className="text-[#71717A]">RESULT: </span>
                                {call.result_preview}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 选项卡 2：评测门禁与版本对比 (Eval & Compare) */}
      {activeTab === 'eval' && (
        <div className="space-y-6">
          {/* 评测版本对比器 */}
          <div className="bg-[#141414] p-4 rounded-sm border border-[rgba(65,65,65,0.8)] space-y-4">
            <div className="flex items-center gap-2 text-white font-bold text-sm uppercase font-mono">
              <GitCompare className="w-4 h-4 text-[#FAFF69]" />
              评测版本对比器 (VERSION DIFF COMPARATOR)
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] text-[#A0A0A0] uppercase font-mono block mb-1">
                  基线版本 BASE RUN
                </label>
                <select
                  value={baseRunId}
                  onChange={(e) => {
                    setBaseRunId(e.target.value);
                    setCompareTriggered(false);
                  }}
                  className="w-full bg-[#0A0A0A] text-xs text-white border border-[rgba(65,65,65,0.8)] rounded-sm p-2 font-mono focus:border-[#FAFF69] focus:outline-none"
                >
                  <option value="">选择 Base Run...</option>
                  {evalRuns.map((r: EvalRunItem) => (
                    <option key={r.id} value={r.id}>
                      {r.dataset_name}@{r.dataset_version} ({r.id.slice(0, 8)}) - 正确率:{' '}
                      {(Number(r.summary?.accuracy ?? 0) * 100).toFixed(1)}%
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] text-[#A0A0A0] uppercase font-mono block mb-1">
                  对比版本 TARGET RUN
                </label>
                <select
                  value={targetRunId}
                  onChange={(e) => {
                    setTargetRunId(e.target.value);
                    setCompareTriggered(false);
                  }}
                  className="w-full bg-[#0A0A0A] text-xs text-white border border-[rgba(65,65,65,0.8)] rounded-sm p-2 font-mono focus:border-[#FAFF69] focus:outline-none"
                >
                  <option value="">选择 Target Run...</option>
                  {evalRuns.map((r: EvalRunItem) => (
                    <option key={r.id} value={r.id}>
                      {r.dataset_name}@{r.dataset_version} ({r.id.slice(0, 8)}) - 正确率:{' '}
                      {(Number(r.summary?.accuracy ?? 0) * 100).toFixed(1)}%
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-end">
                <button
                  disabled={!baseRunId || !targetRunId}
                  onClick={() => setCompareTriggered(true)}
                  className="w-full py-2 bg-[#FAFF69] text-black font-black uppercase text-xs rounded-sm hover:bg-[#F4F692] disabled:opacity-40 transition-colors"
                >
                  执行 DIFF 对比
                </button>
              </div>
            </div>

            {/* 对比结果呈现 */}
            {compareLoading && (
              <div className="text-xs font-mono text-[#A0A0A0]">计算版本差异与回归样本中...</div>
            )}

            {compareData && (
              <div className="space-y-4 pt-3 border-t border-[rgba(65,65,65,0.8)] font-mono">
                {/* 差值卡片 */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-[#0A0A0A] p-3 rounded-sm border border-[rgba(65,65,65,0.8)]">
                    <span className="text-[10px] text-[#A0A0A0] uppercase block">准确率变化 ACCURACY DELTA</span>
                    <span
                      className={`text-lg font-black ${
                        compareData.delta.accuracy_delta >= 0 ? 'text-[#4ADE80]' : 'text-[#FF6B6B]'
                      }`}
                    >
                      {compareData.delta.accuracy_delta > 0 ? '+' : ''}
                      {(compareData.delta.accuracy_delta * 100).toFixed(2)}%
                    </span>
                  </div>

                  <div className="bg-[#0A0A0A] p-3 rounded-sm border border-[rgba(65,65,65,0.8)]">
                    <span className="text-[10px] text-[#A0A0A0] uppercase block">通过题数变化 PASSED DELTA</span>
                    <span
                      className={`text-lg font-black ${
                        compareData.delta.passed_delta >= 0 ? 'text-[#4ADE80]' : 'text-[#FF6B6B]'
                      }`}
                    >
                      {compareData.delta.passed_delta > 0 ? '+' : ''}
                      {compareData.delta.passed_delta} 题
                    </span>
                  </div>

                  <div className="bg-[#0A0A0A] p-3 rounded-sm border border-[#FF6B6B]/40">
                    <span className="text-[10px] text-[#FF6B6B] uppercase block">退化样本 REGRESSIONS</span>
                    <span className="text-lg font-black text-[#FF6B6B]">
                      {compareData.delta.regression_count} 题
                    </span>
                  </div>

                  <div className="bg-[#0A0A0A] p-3 rounded-sm border border-[#4ADE80]/40">
                    <span className="text-[10px] text-[#4ADE80] uppercase block">修复样本 FIXES</span>
                    <span className="text-lg font-black text-[#4ADE80]">
                      {compareData.delta.fixed_count} 题
                    </span>
                  </div>
                </div>

                {/* 样本状态列表 */}
                <div className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] rounded-sm overflow-x-auto max-h-[320px]">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#141414] text-[#A0A0A0] uppercase sticky top-0">
                      <tr>
                        <th className="py-2 px-3">SAMPLE ID</th>
                        <th className="py-2 px-3">STATUS</th>
                        <th className="py-2 px-3">BASE RESULT</th>
                        <th className="py-2 px-3">TARGET RESULT</th>
                        <th className="py-2 px-3">DETAIL</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[rgba(65,65,65,0.5)]">
                      {compareData.samples.map((s) => (
                        <tr
                          key={s.sample_id}
                          className={
                            s.status === 'regression'
                              ? 'bg-[#FF6B6B]/10'
                              : s.status === 'fixed'
                              ? 'bg-[#4ADE80]/10'
                              : ''
                          }
                        >
                          <td className="py-2 px-3 text-white font-bold">{s.sample_id}</td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-1.5 py-0.5 rounded-sm text-[10px] font-bold uppercase ${
                                s.status === 'regression'
                                  ? 'bg-[#FF6B6B] text-black font-black'
                                  : s.status === 'fixed'
                                  ? 'bg-[#4ADE80] text-black font-black'
                                  : 'text-[#A0A0A0]'
                              }`}
                            >
                              {s.status}
                            </span>
                          </td>
                          <td className="py-2 px-3">
                            {s.base_passed ? (
                              <span className="text-[#4ADE80]">PASS</span>
                            ) : (
                              <span className="text-[#FF6B6B]">FAIL</span>
                            )}
                          </td>
                          <td className="py-2 px-3">
                            {s.target_passed ? (
                              <span className="text-[#4ADE80]">PASS</span>
                            ) : (
                              <span className="text-[#FF6B6B]">FAIL</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-[#A0A0A0] truncate max-w-[240px]">
                            {s.target_detail || s.base_detail || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* 评测历史列表 */}
          <div className="space-y-3 font-mono">
            <span className="text-xs font-bold text-[#A0A0A0] uppercase tracking-wider block">
              历史评测执行记录 (EVAL RUNS HISTORY)
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {evalLoading ? (
                <div className="text-xs text-[#A0A0A0]">加载历史评测中...</div>
              ) : !evalRuns.length ? (
                <div className="text-xs text-[#A0A0A0]">暂无历史评测记录</div>
              ) : (
                evalRuns.map((r: EvalRunItem) => (
                  <div
                    key={r.id}
                    className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] hover:border-[#FAFF69] rounded-sm p-3.5 space-y-2 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white uppercase">
                        {r.dataset_name}@{r.dataset_version}
                      </span>
                      <span className="text-[10px] text-[#FAFF69] px-1.5 py-0.5 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)]">
                        {r.mode}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between pt-1">
                      <span className="text-2xl font-black text-[#FAFF69]">
                        {(Number(r.summary?.accuracy ?? 0) * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-[#A0A0A0]">
                        {r.passed} / {r.sample_count} 通过
                      </span>
                    </div>

                    {r.summary?.faithfulness !== undefined && r.summary.faithfulness !== null && (
                      <div className="text-xs text-[#A0A0A0] flex justify-between">
                        <span>忠实度 FAITHFULNESS:</span>
                        <span className="text-white font-bold">
                          {(Number(r.summary.faithfulness) * 100).toFixed(1)}%
                        </span>
                      </div>
                    )}

                    <div className="text-[10px] text-[#71717A] pt-1 border-t border-[rgba(65,65,65,0.5)]">
                      {r.started_at?.slice(0, 19).replace('T', ' ')}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 选项卡 3：评测集资产 (Datasets) */}
      {activeTab === 'datasets' && (
        <div className="space-y-4 font-mono">
          <div className="bg-[#141414] p-3 rounded-sm border border-[rgba(65,65,65,0.8)] text-xs text-[#A0A0A0]">
            评测集由 <code className="text-[#FAFF69]">dataset_catalog</code> 不可变管理。每个版本锁定 SHA-256 内容哈希，保障回归门禁确定性。
          </div>

          <div className="bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] rounded-sm overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#141414] text-[#A0A0A0] uppercase border-b border-[rgba(65,65,65,0.8)]">
                <tr>
                  <th className="py-2.5 px-3">DATASET NAME</th>
                  <th className="py-2.5 px-3">VERSION</th>
                  <th className="py-2.5 px-3">SAMPLES</th>
                  <th className="py-2.5 px-3">CONTENT HASH</th>
                  <th className="py-2.5 px-3">STATUS</th>
                  <th className="py-2.5 px-3">CREATED AT</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(65,65,65,0.5)]">
                {datasetsLoading ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#A0A0A0]">
                      加载中...
                    </td>
                  </tr>
                ) : !datasetsData?.versions.length ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#A0A0A0]">
                      暂无已登记数据集版本
                    </td>
                  </tr>
                ) : (
                  datasetsData.versions.map((d) => (
                    <tr key={d.id || `${d.dataset_name}-${d.version}`} className="hover:bg-[#141414]">
                      <td className="py-2.5 px-3 text-white font-bold">{d.dataset_name}</td>
                      <td className="py-2.5 px-3 text-[#FAFF69] font-bold">{d.version}</td>
                      <td className="py-2.5 px-3 text-white">{d.sample_count} 条</td>
                      <td className="py-2.5 px-3 text-[#A0A0A0]">{d.content_hash.slice(0, 16)}...</td>
                      <td className="py-2.5 px-3">
                        <span className="px-1.5 py-0.5 rounded-sm bg-[#166534] text-[#4ADE80] text-[10px] font-bold">
                          FROZEN / CLEAN
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-[#71717A]">
                        {d.created_at?.slice(0, 19).replace('T', ' ')}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
