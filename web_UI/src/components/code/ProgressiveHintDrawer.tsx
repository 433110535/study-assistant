import React, { useState } from 'react';
import { fetchCodeHint } from '@/lib/api-client';
import {
  Lightbulb,
  Lock,
  Unlock,
  RotateCcw,
  Sparkles,
  HelpCircle,
  Code2,
  CheckCircle,
} from 'lucide-react';

interface ProgressiveHintDrawerProps {
  lastError: string;
  currentCode: string;
}

export const ProgressiveHintDrawer: React.FC<ProgressiveHintDrawerProps> = ({
  lastError,
  currentCode,
}) => {
  const [activeStage, setActiveStage] = useState<number>(1);
  const [hintsCache, setHintsCache] = useState<Record<number, string>>({});
  const [unlockedStages, setUnlockedStages] = useState<number[]>([1]);
  const [forceUnlockAll, setForceUnlockAll] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchHintForStage = async (stage: number) => {
    if (hintsCache[stage]) {
      setActiveStage(stage);
      return;
    }

    setLoading(true);
    try {
      // Assemble observation: error output or fallback
      const observationText = lastError || (currentCode ? `代码内容:\n${currentCode}` : '');
      const res = await fetchCodeHint(stage, observationText);
      setHintsCache((prev) => ({ ...prev, [stage]: res.hint }));
      setActiveStage(stage);

      // Unlock next stage sequentially
      if (stage < 3 && !unlockedStages.includes(stage + 1)) {
        setUnlockedStages((prev) => [...prev, stage + 1]);
      }
    } catch (err: any) {
      alert(`获取提示失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const isStageUnlocked = (stage: number) => {
    return forceUnlockAll || unlockedStages.includes(stage);
  };

  const stagesMeta = [
    {
      stage: 1,
      title: 'STAGE 1: 概念点拨',
      subtitle: 'CONCEPT_NUDGE',
      desc: '提示核心算法思想与边界预设，不暴露代码',
      icon: Lightbulb,
    },
    {
      stage: 2,
      title: 'STAGE 2: 伪代码方向',
      subtitle: 'PSEUDOCODE_PATH',
      desc: '拆解控制流与数据结构逻辑骨架',
      icon: HelpCircle,
    },
    {
      stage: 3,
      title: 'STAGE 3: 根因修复指导',
      subtitle: 'DIAGNOSTIC_FIX',
      desc: '精准指出 Traceback 报错行与修复策略',
      icon: Code2,
    },
  ];

  return (
    <div className="border border-[rgba(65,65,65,0.8)] bg-[#0A0A0A] font-mono text-sm flex flex-col">
      {/* Header */}
      <div className="p-2.5 border-b border-[rgba(65,65,65,0.8)] bg-black flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-[#FAFF69]" />
          <span className="text-xs text-white font-bold tracking-wider">
            SOCRATIC_PROGRESSIVE_HINTS
          </span>
        </div>

        {/* Debug Geek Switch */}
        <label className="flex items-center space-x-1.5 cursor-pointer text-[10px] text-neutral-400 select-none">
          <input
            type="checkbox"
            checked={forceUnlockAll}
            onChange={(e) => setForceUnlockAll(e.target.checked)}
            className="rounded border-neutral-700 text-[#FAFF69] focus:ring-0"
          />
          <span className={forceUnlockAll ? 'text-[#FAFF69]' : ''}>
            [FORCE_UNLOCK_ALL]
          </span>
        </label>
      </div>

      {/* Stage Tabs (Lock / Unlock state machine) */}
      <div className="grid grid-cols-3 border-b border-[rgba(65,65,65,0.8)] bg-black">
        {stagesMeta.map((s) => {
          const unlocked = isStageUnlocked(s.stage);
          const active = activeStage === s.stage;
          const hasCache = !!hintsCache[s.stage];

          return (
            <button
              key={s.stage}
              type="button"
              disabled={!unlocked || loading}
              onClick={() => fetchHintForStage(s.stage)}
              className={`p-2.5 text-left border-r last:border-r-0 border-[rgba(65,65,65,0.8)] transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
                active
                  ? 'bg-[#0A0A0A] border-b-2 border-b-[#FAFF69]'
                  : 'hover:bg-white/[0.02]'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center space-x-1">
                  <span>L{s.stage}</span>
                </span>
                {unlocked ? (
                  hasCache ? (
                    <CheckCircle className="w-3 h-3 text-[#4ADE80]" />
                  ) : (
                    <Unlock className="w-3 h-3 text-[#FAFF69]" />
                  )
                ) : (
                  <Lock className="w-3 h-3 text-neutral-600" />
                )}
              </div>
              <div className="text-[10px] text-neutral-400 mt-1 truncate">
                {s.subtitle}
              </div>
            </button>
          );
        })}
      </div>

      {/* Active Stage Content */}
      <div className="p-4 bg-[#0A0A0A] min-h-[180px] max-h-[300px] overflow-y-auto space-y-3">
        {loading ? (
          <div className="flex flex-col items-center justify-center p-8 space-y-2 text-[#FAFF69]">
            <RotateCcw className="w-5 h-5 animate-spin" />
            <span className="text-xs">[GENERATING_SOCRATIC_STAGE_HINT...]</span>
          </div>
        ) : hintsCache[activeStage] ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs pb-1 border-b border-neutral-800">
              <span className="text-[#FAFF69] font-bold">
                [{stagesMeta[activeStage - 1].title}]
              </span>
              <span className="text-[10px] text-neutral-500">
                {stagesMeta[activeStage - 1].desc}
              </span>
            </div>
            <div className="text-xs text-neutral-200 whitespace-pre-wrap break-all font-sans leading-relaxed">
              {hintsCache[activeStage]}
            </div>
          </div>
        ) : (
          <div className="p-6 text-center text-neutral-500 space-y-3">
            <div className="text-xs">
              当前尚未生成 {stagesMeta[activeStage - 1].title}
            </div>
            <p className="text-[10px] text-neutral-600 max-w-xs mx-auto">
              苏格拉底教学理念：先独立思考，遇到瓶颈再逐步点亮各级提示。
            </p>
            <button
              type="button"
              disabled={loading}
              onClick={() => fetchHintForStage(activeStage)}
              className="px-4 py-1.5 bg-[#FAFF69] text-black text-xs font-bold uppercase tracking-wider hover:brightness-110"
            >
              FETCH_STAGE_{activeStage}_HINT
            </button>
          </div>
        )}
      </div>

      {/* Observation context bar */}
      <div className="px-3 py-1.5 bg-black border-t border-[rgba(65,65,65,0.8)] text-[10px] text-neutral-500 flex items-center justify-between">
        <span>CONTEXT: {lastError ? 'ATTACHED_STDERR' : 'STANDALONE_CODE'}</span>
        <button
          type="button"
          disabled={loading}
          onClick={() => {
            setHintsCache({});
            setUnlockedStages([1]);
            fetchHintForStage(1);
          }}
          className="text-neutral-400 hover:text-white"
        >
          [RESET_HINTS]
        </button>
      </div>
    </div>
  );
};
