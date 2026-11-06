import React, { useState, useEffect } from 'react';
import { fetchMastery } from '@/lib/api-client';
import { MasteryItem } from '@/types/review';
import {
  RotateCcw,
  Sparkles,
  AlertTriangle,
  CheckCircle,
  ArrowUpRight,
} from 'lucide-react';

interface MasteryRadarTabProps {
  onNavigateToPractice?: (concept: string) => void;
}

export const MasteryRadarTab: React.FC<MasteryRadarTabProps> = ({
  onNavigateToPractice,
}) => {
  const [items, setItems] = useState<MasteryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchMastery('student');
      setItems(data);
    } catch (err: any) {
      console.error('Failed to load mastery data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const totalConcepts = items.length;
  const avgScore = totalConcepts
    ? items.reduce((acc, it) => acc + it.score, 0) / totalConcepts
    : 0;

  const criticalCount = items.filter((it) => it.score < 0.4).length;
  const consolidatingCount = items.filter(
    (it) => it.score >= 0.4 && it.score < 0.75
  ).length;
  const masteredCount = items.filter((it) => it.score >= 0.75).length;

  return (
    <div className="space-y-4 font-mono text-sm">
      {/* Overview Metric Banner */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider">
            TRACKED_CONCEPTS
          </div>
          <div className="text-xl font-bold text-white mt-1">{totalConcepts}</div>
        </div>

        <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A]">
          <div className="text-[10px] text-neutral-500 uppercase tracking-wider">
            AVG_MASTERY_RATE
          </div>
          <div className="text-xl font-bold text-[#FAFF69] mt-1">
            {(avgScore * 100).toFixed(1)}%
          </div>
        </div>

        <div className="p-3 border border-red-900/50 bg-[#0A0A0A]">
          <div className="text-[10px] text-red-400 uppercase tracking-wider flex items-center space-x-1">
            <AlertTriangle className="w-3 h-3 text-red-400" />
            <span>CRITICAL_WEAKNESS</span>
          </div>
          <div className="text-xl font-bold text-red-400 mt-1">{criticalCount}</div>
        </div>

        <div className="p-3 border border-[#FAFF69]/50 bg-[#0A0A0A]">
          <div className="text-[10px] text-[#FAFF69] uppercase tracking-wider">
            CONSOLIDATING
          </div>
          <div className="text-xl font-bold text-[#FAFF69] mt-1">{consolidatingCount}</div>
        </div>

        <div className="p-3 border border-[#4ADE80]/40 bg-[#0A0A0A]">
          <div className="text-[10px] text-[#4ADE80] uppercase tracking-wider flex items-center space-x-1">
            <CheckCircle className="w-3 h-3 text-[#4ADE80]" />
            <span>SOLID_MASTERED</span>
          </div>
          <div className="text-xl font-bold text-[#4ADE80] mt-1">{masteredCount}</div>
        </div>
      </div>

      {/* Control Header */}
      <div className="p-3 border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] flex items-center justify-between">
        <div className="text-xs text-neutral-400 flex items-center space-x-2">
          <Sparkles className="w-3.5 h-3.5 text-[#FAFF69]" />
          <span>KNOWLEDGE POINT MASTERY SPECTRUM (SORTED BY WEAKNESS FIRST)</span>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="p-1 border border-[rgba(65,65,65,0.8)] text-neutral-400 hover:text-white"
          title="Reload Mastery"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Concept Mastery List */}
      {loading ? (
        <div className="p-12 text-center border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-500">
          [COMPUTING_CONCEPT_MASTERY_VECTORS...]
        </div>
      ) : items.length === 0 ? (
        <div className="p-12 text-center border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] text-neutral-500 space-y-2">
          <div>NO_MASTERY_DATA_RECORDED_YET</div>
          <p className="text-xs text-neutral-600">
            当学生在题库中完成单题练习、整卷批改或 SM-2 抽认卡复习后，系统将自动汇总更新考点掌握度。
          </p>
        </div>
      ) : (
        <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] divide-y divide-[rgba(65,65,65,0.8)]">
          {items.map((item) => {
            const scorePct = Math.round(item.score * 100);
            const isCritical = item.score < 0.4;
            const isConsolidating = item.score >= 0.4 && item.score < 0.75;

            let badgeColor = '';
            let badgeText = '';
            let barColor = '';

            if (isCritical) {
              badgeColor = 'border-red-500/60 bg-red-950/30 text-red-400';
              badgeText = 'CRITICAL_WEAKNESS';
              barColor = 'bg-[#F87171]';
            } else if (isConsolidating) {
              badgeColor = 'border-[#FAFF69]/60 bg-[#FAFF69]/10 text-[#FAFF69]';
              badgeText = 'CONSOLIDATING';
              barColor = 'bg-[#FAFF69]';
            } else {
              badgeColor = 'border-[#4ADE80]/60 bg-[#4ADE80]/10 text-[#4ADE80]';
              badgeText = 'MASTERED';
              barColor = 'bg-[#4ADE80]';
            }

            return (
              <div
                key={item.concept}
                className="p-4 hover:bg-white/[0.02] transition-colors space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-white font-sans">
                      {item.concept}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 border text-[10px] font-bold ${badgeColor}`}
                    >
                      [{badgeText}]
                    </span>
                  </div>

                  <div className="flex items-center space-x-3 text-xs">
                    <span className="text-neutral-500">
                      ATTEMPTS: {item.attempts}
                    </span>
                    <span className="text-neutral-500">|</span>
                    <span className="text-neutral-400">
                      LAST_SEEN: {item.last_seen ? new Date(item.last_seen).toLocaleDateString() : 'N/A'}
                    </span>
                    {onNavigateToPractice && (
                      <button
                        type="button"
                        onClick={() => onNavigateToPractice(item.concept)}
                        className="px-2 py-0.5 border border-[#FAFF69] text-[#FAFF69] hover:bg-[#FAFF69] hover:text-black text-[10px] font-bold flex items-center space-x-1 uppercase"
                      >
                        <span>GENERATE_TARGETED_PRACTICE</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Industrial High-Contrast Progress Bar */}
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-neutral-400 font-mono">
                    <span>MASTERY_CONFIDENCE</span>
                    <span className="font-bold text-white">{scorePct}%</span>
                  </div>
                  <div className="w-full h-2 bg-black border border-[rgba(65,65,65,0.8)] overflow-hidden">
                    <div
                      className={`h-full ${barColor} transition-all duration-300`}
                      style={{ width: `${Math.min(100, Math.max(4, scorePct))}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
