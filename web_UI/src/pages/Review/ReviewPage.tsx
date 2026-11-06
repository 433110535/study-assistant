import React, { useState } from 'react';
import { DueReviewDeckTab } from '@/components/review/DueReviewDeckTab';
import { MistakeRegistryTab } from '@/components/review/MistakeRegistryTab';
import { MasteryRadarTab } from '@/components/review/MasteryRadarTab';
import { BookOpen, Layers, Target } from 'lucide-react';

interface ReviewPageProps {
  onNavigate?: (path: string) => void;
}

export const ReviewPage: React.FC<ReviewPageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<'deck' | 'registry' | 'mastery'>('deck');
  const [targetMistakeId, setTargetMistakeId] = useState<string | null>(null);

  const handlePracticeMistake = (mistakeId: string) => {
    setTargetMistakeId(mistakeId);
    setActiveTab('deck');
  };

  const handleNavigateToPractice = (_concept: string) => {
    // Navigate to practice page
    onNavigate?.('/practice');
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="border-b border-[rgba(65,65,65,0.8)] pb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-[#FAFF69] tracking-widest uppercase">
            <span>[MODULE: M4 / M5]</span>
            <span>•</span>
            <span>SM-2 SPACED REPETITION ENGINE</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white mt-1 uppercase font-mono">
            REVIEW & SPACED-REPETITION WORKBENCH
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            基于艾宾浩斯遗忘曲线与 SM-2 算法的智能错题轮转、人工审核建档与考点掌握度全景雷达
          </p>
        </div>

        {/* Workspace Mode Subtabs */}
        <div className="flex items-center space-x-1 border border-[rgba(65,65,65,0.8)] p-1 bg-[#0A0A0A] font-mono text-xs">
          <button
            type="button"
            onClick={() => {
              setActiveTab('deck');
            }}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'deck'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>[DUE_REVIEW_DECK]</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('registry')}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'registry'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>[MISTAKE_REGISTRY]</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('mastery')}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'mastery'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Target className="w-3.5 h-3.5" />
            <span>[MASTERY_RADAR]</span>
          </button>
        </div>
      </div>

      {/* Tab Panels */}
      {activeTab === 'deck' && (
        <DueReviewDeckTab
          onSwitchTab={(t) => setActiveTab(t)}
          targetMistakeId={targetMistakeId}
          onClearTargetMistake={() => setTargetMistakeId(null)}
        />
      )}

      {activeTab === 'registry' && (
        <MistakeRegistryTab
          onPracticeMistake={handlePracticeMistake}
        />
      )}

      {activeTab === 'mastery' && (
        <MasteryRadarTab
          onNavigateToPractice={handleNavigateToPractice}
        />
      )}
    </div>
  );
};
export default ReviewPage;
