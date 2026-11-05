import React from 'react';
import { Menu, RefreshCw, Cpu, Database } from 'lucide-react';

interface TopbarProps {
  currentPath: string;
  onOpenMobileNav: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

const PATH_TITLES: Record<string, string> = {
  '/': 'OVERVIEW // 学习数据概览',
  '/chat': 'CHAT // 智能答疑会话',
  '/practice': 'PRACTICE // 题库自测训练',
  '/review': 'REVIEW // 艾宾浩斯错题复习',
  '/knowledge': 'KNOWLEDGE // 知识库文档检索',
  '/code': 'CODE // Python 代码助教沙箱',
};

export const Topbar: React.FC<TopbarProps> = ({
  currentPath,
  onOpenMobileNav,
  onRefresh,
  isRefreshing = false,
}) => {
  const title = PATH_TITLES[currentPath] || 'OVERVIEW // 学习数据概览';

  return (
    <header className="h-[56px] px-4 md:px-8 bg-[#0A0A0A] border-b border-[rgba(65,65,65,0.8)] flex items-center justify-between shrink-0 select-none">
      {/* 左侧：移动端呼出抽屉 + 面包屑 */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileNav}
          className="p-1.5 -ml-1 rounded-sm text-[#A1A1AA] hover:text-white hover:bg-[#141414] border border-[rgba(65,65,65,0.8)] md:hidden focus:outline-none"
          aria-label="打开导航菜单"
        >
          <Menu className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-black tracking-label text-white uppercase">
            {title}
          </span>
        </div>
      </div>

      {/* 右侧：状态指示、刷新与环境标签 */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* API 状态指示器 */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)]">
          <div className="w-1.5 h-1.5 rounded-full bg-[#FAFF69] animate-pulse" />
          <span className="font-mono text-[11px] font-bold tracking-label text-[#A1A1AA] uppercase">
            ENGINE ONLINE
          </span>
          <span className="font-mono text-[10px] text-[#71717A]">
            /v1
          </span>
        </div>

        {/* 知识库状态胶囊 */}
        <div className="hidden lg:flex items-center gap-1.5 px-2 py-1 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] text-[#A1A1AA]">
          <Database className="w-3 h-3 text-[#FAFF69]" />
          <span className="font-mono text-[10px] tracking-label">RAG READY</span>
        </div>

        {/* 刷新动作按钮 */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#141414] hover:bg-[#1f1f1f] border border-[rgba(65,65,65,0.8)] hover:border-[#FAFF69] text-white text-xs font-mono transition-colors disabled:opacity-50"
            title="刷新数据"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#FAFF69]' : 'text-[#A1A1AA]'}`} />
            <span className="hidden sm:inline text-[11px] uppercase tracking-label">SYNC</span>
          </button>
        )}

        {/* 本地学生标签 */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-sm bg-[#FAFF69]/10 border border-[#FAFF69]/40 text-[#FAFF69]">
          <Cpu className="w-3 h-3" />
          <span className="font-mono text-[10px] font-bold tracking-label uppercase">
            LOCAL
          </span>
        </div>
      </div>
    </header>
  );
};
