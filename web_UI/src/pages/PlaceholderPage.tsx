import React from 'react';
import { Hammer, ArrowLeft } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  phase: string;
  description: string;
  onBack: () => void;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  phase,
  description,
  onBack,
}) => {
  return (
    <div className="py-20 px-6 max-w-xl mx-auto rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] text-center">
      <div className="w-12 h-12 rounded-sm bg-[#FAFF69]/10 border border-[#FAFF69]/30 flex items-center justify-center mx-auto mb-4">
        <Hammer className="w-6 h-6 text-[#FAFF69]" />
      </div>

      <span className="inline-block px-2 py-0.5 rounded-sm bg-black border border-[rgba(65,65,65,0.8)] text-[#FAFF69] font-mono text-xs font-bold uppercase tracking-label mb-3">
        PHASE {phase} IN PIPELINE
      </span>

      <h2 className="text-xl font-black text-white uppercase tracking-tight mb-2">
        {title}
      </h2>

      <p className="text-xs text-[#A1A1AA] font-mono mb-6 max-w-md mx-auto">
        {description}
      </p>

      <button
        onClick={onBack}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-black hover:bg-[#1a1a1a] border border-[rgba(65,65,65,0.8)] text-white font-mono text-xs font-bold uppercase tracking-label transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>返回概览仪表盘 (OVERVIEW)</span>
      </button>
    </div>
  );
};
