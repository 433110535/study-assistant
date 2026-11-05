import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSummary } from '@/lib/api-client';
import { MetricGrid } from './MetricGrid';
import { MasteryBucketChart } from './MasteryBucketChart';
import { MistakeStatusCard } from './MistakeStatusCard';
import { RecentRunsTable } from './RecentRunsTable';
import { ArrowRight, Sparkles, AlertCircle, RefreshCw } from 'lucide-react';

interface OverviewPageProps {
  onNavigate: (path: string) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchOnWindowFocus: false,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        {/* Banner 骨架 */}
        <div className="h-32 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm animate-pulse" />
        {/* 指标卡骨架 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm animate-pulse" />
          ))}
        </div>
        {/* 中间图表骨架 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-64 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm animate-pulse" />
          <div className="h-64 bg-[#141414] border border-[rgba(65,65,65,0.8)] rounded-sm animate-pulse" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="py-16 px-6 max-w-xl mx-auto rounded-sm bg-[#141414] border border-[#EF4444]/60 text-center">
        <AlertCircle className="w-10 h-10 text-[#EF4444] mx-auto mb-3" />
        <h3 className="font-mono text-sm font-black tracking-label text-white uppercase mb-2">
          GET /v1/dashboard/summary 连接异常
        </h3>
        <p className="text-xs text-[#A1A1AA] mb-4 font-mono break-all">
          {error instanceof Error ? error.message : '请确认本地 127.0.0.1:8000 后端已正常启动'}
        </p>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-[#FAFF69] text-black font-mono text-xs font-bold uppercase tracking-label hover:bg-[#F4F692] transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          <span>重新尝试连接</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 顶部 Action Hero Banner */}
      <div className="p-6 md:p-8 rounded-sm bg-[#0A0A0A] border border-[rgba(65,65,65,0.8)] flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] text-[#FAFF69] text-xs font-mono font-bold tracking-label uppercase mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI TUTOR WORKSPACE // 2.0</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight uppercase">
            智能导学与记忆中枢
          </h1>
          <p className="text-xs md:text-sm text-[#A1A1AA] mt-1.5 max-w-2xl">
            ClickHouse 极速交互风格 · 整合 RAG 知识检索、多轮代码沙箱诊断与艾宾浩斯抗遗忘系统
          </p>
        </div>

        {/* 快速动作入口 */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => onNavigate('/review')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-sm bg-[#FAFF69] hover:bg-[#F4F692] text-black text-xs font-mono font-black uppercase tracking-label transition-colors"
          >
            <span>开始今日复习</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <button
            onClick={() => onNavigate('/chat')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-sm bg-[#141414] hover:bg-[#1f1f1f] border border-[rgba(65,65,65,0.8)] hover:border-white text-white text-xs font-mono font-bold uppercase tracking-label transition-colors"
          >
            <span>开启智能对话</span>
          </button>
        </div>
      </div>

      {/* 核心指标 4 格网格 */}
      <section aria-label="核心指标">
        <MetricGrid data={data} />
      </section>

      {/* 掌握度分布与错题流转管线 */}
      <section aria-label="深度分析" className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MasteryBucketChart mastery={data.mastery} />
        <MistakeStatusCard
          mistakes={data.mistakes}
          onGoToReview={() => onNavigate('/review')}
        />
      </section>

      {/* 最近执行流水表 */}
      <section aria-label="引擎执行流水">
        <RecentRunsTable runs={data.recent_runs} />
      </section>
    </div>
  );
};
