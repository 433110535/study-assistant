import React, { useState } from 'react';
import { FileText, FlaskConical, Wand2 } from 'lucide-react';
import { PaperGradingTab } from '@/components/practice/PaperGradingTab';
import { SingleItemLabTab } from '@/components/practice/SingleItemLabTab';
import { QuestionGeneratorTab } from '@/components/practice/QuestionGeneratorTab';

type TabType = 'paper' | 'single' | 'generator';

interface PracticePageProps {
  onNavigate?: (path: string) => void;
}

export const PracticePage: React.FC<PracticePageProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<TabType>('paper');

  // 跨 Tab 状态传递（从整卷未判题快速转入单题实验室）
  const [singleLabInitial, setSingleLabInitial] = useState<{
    question: string;
    studentAnswer: string;
  }>({ question: '', studentAnswer: '' });

  const handleOpenInSingleLab = (question: string, studentAnswer: string) => {
    setSingleLabInitial({ question, studentAnswer });
    setActiveTab('single');
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg font-mono">
      {/* 顶部 Tab 导航栏 (ClickHouse 底线风格) */}
      <div className="h-12 px-4 md:px-6 border-b border-border bg-surface flex items-center justify-between shrink-0 text-xs">
        <div className="flex items-center gap-1 md:gap-4 h-full">
          <button
            onClick={() => setActiveTab('paper')}
            className={`h-full flex items-center gap-2 px-3 border-b-2 font-bold uppercase tracking-label transition-colors ${
              activeTab === 'paper'
                ? 'border-accent text-accent'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>整卷智能批改 (FULL_PAPER)</span>
          </button>

          <button
            onClick={() => setActiveTab('single')}
            className={`h-full flex items-center gap-2 px-3 border-b-2 font-bold uppercase tracking-label transition-colors ${
              activeTab === 'single'
                ? 'border-accent text-accent'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>单题诊断与变式 (SINGLE_LAB)</span>
          </button>

          <button
            onClick={() => setActiveTab('generator')}
            className={`h-full flex items-center gap-2 px-3 border-b-2 font-bold uppercase tracking-label transition-colors ${
              activeTab === 'generator'
                ? 'border-accent text-accent'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            <Wand2 className="w-3.5 h-3.5" />
            <span>AI 靶向出题自测 (GENERATOR)</span>
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-[11px] text-text-muted">
          <span>工作台模式:</span>
          <span className="text-accent uppercase font-bold">PRACTICE_V3</span>
        </div>
      </div>

      {/* Tab 主体展示 */}
      <div className="flex-1 flex overflow-hidden">
        {activeTab === 'paper' && (
          <PaperGradingTab
            onOpenInSingleLab={handleOpenInSingleLab}
            onNavigateToMistakes={() => onNavigate?.('/review')}
          />
        )}
        {activeTab === 'single' && (
          <SingleItemLabTab
            initialQuestion={singleLabInitial.question}
            initialStudentAnswer={singleLabInitial.studentAnswer}
          />
        )}
        {activeTab === 'generator' && <QuestionGeneratorTab />}
      </div>
    </div>
  );
};
