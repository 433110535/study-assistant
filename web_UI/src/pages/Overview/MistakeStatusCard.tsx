import React from 'react';
import { MistakeStats } from '@/types/dashboard';
import { RotateCcw, Clock, CheckCircle2, XCircle, ArrowUpRight } from 'lucide-react';

interface MistakeStatusCardProps {
  mistakes: MistakeStats;
  onGoToReview?: () => void;
}

export const MistakeStatusCard: React.FC<MistakeStatusCardProps> = ({
  mistakes,
  onGoToReview,
}) => {
  const { total, pending, confirmed, dismissed, due_today } = mistakes;

  return (
    <div className="p-4 md:p-6 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] flex flex-col justify-between">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-[#FAFF69]" />
            <h3 className="font-mono text-xs font-black tracking-label text-white uppercase">
              MISTAKE PIPELINE // 错题状态流转
            </h3>
          </div>
          <p className="text-xs text-[#A1A1AA] mt-1">
            艾宾浩斯记忆曲线调度与掌握状态
          </p>
        </div>

        {due_today > 0 && (
          <span className="px-2 py-0.5 rounded-sm bg-[#FAFF69] text-black font-mono text-[11px] font-bold uppercase tracking-label">
            {due_today} DUE TODAY
          </span>
        )}
      </div>

      {/* 错题状态四格矩阵 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 my-2">
        {/* 全部错题 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="text-[10px] font-mono text-[#71717A] uppercase tracking-label mb-1">
            ALL MISTAKES
          </div>
          <div className="font-mono text-xl font-black text-white">
            {total}
          </div>
          <div className="text-[10px] font-mono text-[#A1A1AA] mt-0.5">累计入库</div>
        </div>

        {/* 待复习 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-[#FAFF69] uppercase tracking-label">
              PENDING
            </span>
            <Clock className="w-3 h-3 text-[#FAFF69]" />
          </div>
          <div className="font-mono text-xl font-black text-[#FAFF69]">
            {pending}
          </div>
          <div className="text-[10px] font-mono text-[#71717A] mt-0.5">排队待背</div>
        </div>

        {/* 巩固中 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-[#38BDF8] uppercase tracking-label">
              CONFIRMED
            </span>
            <CheckCircle2 className="w-3 h-3 text-[#38BDF8]" />
          </div>
          <div className="font-mono text-xl font-black text-white">
            {confirmed}
          </div>
          <div className="text-[10px] font-mono text-[#71717A] mt-0.5">多轮练习中</div>
        </div>

        {/* 已攻克 / 归档 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-[#71717A] uppercase tracking-label">
              DISMISSED
            </span>
            <XCircle className="w-3 h-3 text-[#71717A]" />
          </div>
          <div className="font-mono text-xl font-black text-[#71717A]">
            {dismissed}
          </div>
          <div className="text-[10px] font-mono text-[#71717A] mt-0.5">已消灭 / 移除</div>
        </div>
      </div>

      {/* 底部复习触发操作条 */}
      <div className="mt-4 pt-3 border-t border-[rgba(65,65,65,0.4)] flex items-center justify-between">
        <span className="text-xs text-[#A1A1AA] font-mono">
          {due_today > 0 ? `当前有 ${due_today} 道错题已达到复习周期` : '暂无到期需温习的题目'}
        </span>

        {onGoToReview && (
          <button
            onClick={onGoToReview}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#166534] hover:bg-[#15803d] text-white text-xs font-mono font-bold uppercase tracking-label transition-colors"
          >
            <span>进入复习</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};
