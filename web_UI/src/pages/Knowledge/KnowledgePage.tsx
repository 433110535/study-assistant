import React, { useState } from 'react';
import { DocumentManagerTab } from '@/components/knowledge/DocumentManagerTab';
import { VectorSearchLabTab } from '@/components/knowledge/VectorSearchLabTab';
import { KnowledgeQaTab } from '@/components/knowledge/KnowledgeQaTab';
import { FolderGit2, Search, MessageSquare } from 'lucide-react';

interface KnowledgePageProps {
  onNavigate?: (path: string) => void;
}

export const KnowledgePage: React.FC<KnowledgePageProps> = () => {
  const [activeTab, setActiveTab] = useState<'manager' | 'search' | 'qa'>('manager');
  const [totalDocuments, setTotalDocuments] = useState<number>(0);
  const [qaQuery, setQaQuery] = useState<string>('');

  const handleSendQueryToQa = (query: string) => {
    setQaQuery(query);
    setActiveTab('qa');
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="border-b border-[rgba(65,65,65,0.8)] pb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-[#FAFF69] tracking-widest uppercase">
            <span>[MODULE: RAG KNOWLEDGE BASE]</span>
            <span>•</span>
            <span>FAISS VECTOR INDEX ENGINE</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white mt-1 uppercase font-mono">
            KNOWLEDGE BASE & RAG WORKBENCH
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            课件教材 PDF 切片入库、FAISS 向量倒排相似度检索与大模型增强问答一体化工作台
          </p>
        </div>

        {/* Subtabs Selector */}
        <div className="flex items-center space-x-1 border border-[rgba(65,65,65,0.8)] p-1 bg-[#0A0A0A] font-mono text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('manager')}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'manager'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <FolderGit2 className="w-3.5 h-3.5" />
            <span>[DOCUMENT_MANAGER]</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('search')}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'search'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            <span>[VECTOR_SEARCH_LAB]</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('qa')}
            className={`px-3 py-1.5 flex items-center space-x-1.5 transition-colors cursor-pointer ${
              activeTab === 'qa'
                ? 'bg-[#FAFF69] text-black font-bold'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>[RAG_QA_WORKBENCH]</span>
          </button>
        </div>
      </div>

      {/* Tab Panels */}
      {activeTab === 'manager' && (
        <DocumentManagerTab
          onIndexUpdated={(count) => setTotalDocuments(count)}
        />
      )}

      {activeTab === 'search' && (
        <VectorSearchLabTab
          totalDocuments={totalDocuments}
          onSendQueryToQa={handleSendQueryToQa}
          onSwitchToManager={() => setActiveTab('manager')}
        />
      )}

      {activeTab === 'qa' && (
        <KnowledgeQaTab
          totalDocuments={totalDocuments}
          initialQuery={qaQuery}
          onSwitchToManager={() => setActiveTab('manager')}
        />
      )}
    </div>
  );
};
export default KnowledgePage;
