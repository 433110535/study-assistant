import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {
  LayoutDashboard,
  MessageSquare,
  PenTool,
  RotateCcw,
  BookOpen,
  Code2,
  ChevronLeft,
  ChevronRight,
  X,
  Terminal,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: React.ElementType;
  phase?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: '概览 OVERVIEW', path: '/', icon: LayoutDashboard },
  { id: 'chat', label: '对话 CHAT', path: '/chat', icon: MessageSquare, phase: 'U2' },
  { id: 'practice', label: '练习 PRACTICE', path: '/practice', icon: PenTool, phase: 'U3' },
  { id: 'review', label: '错题复习 REVIEW', path: '/review', icon: RotateCcw, phase: 'U4' },
  { id: 'knowledge', label: '知识库 KNOWLEDGE', path: '/knowledge', icon: BookOpen, phase: 'U4' },
  { id: 'code', label: '代码助教 CODE', path: '/code', icon: Code2, phase: 'U5' },
];

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
  mobileOpen,
  onMobileOpenChange,
}) => {
  const renderNavContent = (collapsed: boolean) => (
    <div className="flex flex-col h-full bg-[#0A0A0A] border-r border-[rgba(65,65,65,0.8)] select-none">
      {/* 顶部 Logo 区 (56px) */}
      <div className="h-[56px] px-4 flex items-center justify-between border-b border-[rgba(65,65,65,0.8)]">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-6 h-6 rounded-sm bg-[#FAFF69] flex items-center justify-center shrink-0">
            <Terminal className="w-3.5 h-3.5 text-black stroke-[3]" />
          </div>
          {!collapsed && (
            <span className="font-mono font-black text-xs tracking-label uppercase text-white truncate">
              STUDY.ASSISTANT
            </span>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          className="hidden lg:flex items-center justify-center w-6 h-6 rounded-sm text-[#A1A1AA] hover:text-white hover:bg-[#141414] border border-transparent hover:border-[rgba(65,65,65,0.8)] transition-colors"
          title={collapsed ? '展开侧栏' : '收起侧栏'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* 导航项列表 */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = currentPath === item.path;
          return (
            <button
              key={item.path}
              onClick={() => onNavigate(item.path)}
              className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-sm text-xs font-bold uppercase tracking-label transition-colors ${
                isActive
                  ? 'bg-[#141414] text-[#FAFF69]'
                  : 'text-[#A1A1AA] hover:bg-[#141414] hover:text-white'
              }`}
            >
              {/* 选中态左侧 2px 霓虹条 */}
              {isActive && (
                <span className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#FAFF69]" />
              )}
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#FAFF69]' : ''}`} />
              {!collapsed && (
                <div className="flex items-center justify-between flex-1 truncate">
                  <span className="truncate">{item.label}</span>
                  {item.phase && (
                    <span className="text-[10px] font-mono px-1 py-0.2 rounded-sm bg-black border border-[rgba(65,65,65,0.8)] text-[#71717A]">
                      {item.phase}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* 底部模式与运行态 */}
      <div className="p-3 border-t border-[rgba(65,65,65,0.8)]">
        <div className="px-2.5 py-2 rounded-sm bg-[#141414] border border-[rgba(65,65,65,0.8)] flex items-center justify-between">
          <span className="font-mono text-[11px] font-bold text-[#A1A1AA] uppercase tracking-label">
            {collapsed ? 'LOC' : 'AUTH: LOCAL (STUDENT)'}
          </span>
          <span className="w-2 h-2 rounded-full bg-[#FAFF69]" />
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* 桌面视图 (1024px+ 可收缩) */}
      <aside
        className={`hidden md:block shrink-0 transition-[width] duration-150 ${
          isCollapsed ? 'w-[64px]' : 'w-[248px]'
        }`}
      >
        <div className="sticky top-0 h-screen">{renderNavContent(isCollapsed)}</div>
      </aside>

      {/* 390px 移动端抽屉 (Radix Dialog) */}
      <Dialog.Root open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/85 z-40 md:hidden" />
          <Dialog.Content className="fixed top-0 left-0 bottom-0 w-[248px] bg-[#0A0A0A] z-50 md:hidden focus:outline-none">
            <div className="absolute right-2 top-3 z-10">
              <Dialog.Close className="p-1.5 rounded-sm text-[#A1A1AA] hover:text-white bg-[#141414] border border-[rgba(65,65,65,0.8)]">
                <X className="w-4 h-4" />
              </Dialog.Close>
            </div>
            {renderNavContent(false)}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
};
