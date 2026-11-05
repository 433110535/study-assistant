import React from 'react';
import { MasteryStats } from '@/types/dashboard';
import { BarChart3 } from 'lucide-react';

interface MasteryBucketChartProps {
  mastery: MasteryStats;
}

export const MasteryBucketChart: React.FC<MasteryBucketChartProps> = ({ mastery }) => {
  const { distribution, total_concepts, average_score } = mastery;
  const total = total_concepts > 0 ? total_concepts : 1;

  const lowPct = Math.round((distribution.low / total) * 100);
  const medPct = Math.round((distribution.medium / total) * 100);
  const highPct = Math.max(0, 100 - lowPct - medPct);

  const avgDisplay = average_score <= 1.0 ? Math.round(average_score * 100) : Math.round(average_score);

  return (
    <div className="p-4 md:p-6 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] flex flex-col justify-between">
      {/* 头部信息 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#FAFF69]" />
            <h3 className="font-mono text-xs font-black tracking-label text-white uppercase">
              MASTERY DISTRIBUTION // 知识点熟练度梯队
            </h3>
          </div>
          <p className="text-xs text-[#A1A1AA] mt-1">
            基于历史题目作答与概念反刍的贝叶斯/权重分桶
          </p>
        </div>

        <div className="text-right">
          <span className="font-mono text-2xl font-black text-[#FAFF69]">
            {avgDisplay}%
          </span>
          <div className="text-[10px] font-mono text-[#71717A] uppercase tracking-label">
            AVG SCORE
          </div>
        </div>
      </div>

      {/* 极简无渐变分段条 (ClickHouse Segmented Bar) */}
      <div className="w-full h-4 bg-black rounded-sm border border-[rgba(65,65,65,0.8)] flex overflow-hidden my-4">
        {lowPct > 0 && (
          <div
            style={{ width: `${lowPct}%` }}
            className="h-full bg-[#EF4444] border-r border-black"
            title={`薄弱待查: ${distribution.low} (${lowPct}%)`}
          />
        )}
        {medPct > 0 && (
          <div
            style={{ width: `${medPct}%` }}
            className="h-full bg-[#71717A] border-r border-black"
            title={`稳步提升: ${distribution.medium} (${medPct}%)`}
          />
        )}
        {highPct > 0 && (
          <div
            style={{ width: `${highPct}%` }}
            className="h-full bg-[#FAFF69]"
            title={`熟练精通: ${distribution.high} (${highPct}%)`}
          />
        )}
      </div>

      {/* 三列分档数据看板 */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[rgba(65,65,65,0.4)]">
        {/* 薄弱 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono font-bold text-[#EF4444] uppercase tracking-label">
              NEEDS WORK
            </span>
            <span className="w-2 h-2 rounded-full bg-[#EF4444]" />
          </div>
          <div className="font-mono text-lg font-bold text-white">
            {distribution.low}
          </div>
          <div className="text-[10px] font-mono text-[#71717A]">
            &lt; 40% ({lowPct}%)
          </div>
        </div>

        {/* 中等 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono font-bold text-[#A1A1AA] uppercase tracking-label">
              DEVELOPING
            </span>
            <span className="w-2 h-2 rounded-full bg-[#71717A]" />
          </div>
          <div className="font-mono text-lg font-bold text-white">
            {distribution.medium}
          </div>
          <div className="text-[10px] font-mono text-[#71717A]">
            40-75% ({medPct}%)
          </div>
        </div>

        {/* 精通 */}
        <div className="p-2.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono font-bold text-[#FAFF69] uppercase tracking-label">
              MASTERED
            </span>
            <span className="w-2 h-2 rounded-full bg-[#FAFF69]" />
          </div>
          <div className="font-mono text-lg font-bold text-white">
            {distribution.high}
          </div>
          <div className="text-[10px] font-mono text-[#71717A]">
            &gt; 75% ({highPct}%)
          </div>
        </div>
      </div>
    </div>
  );
};
