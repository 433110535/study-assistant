import React, { useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/Overview';
import { PlaceholderPage } from './pages/PlaceholderPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 秒缓存
      retry: 1,
    },
  },
});

const AppContent: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>('/');
  const qc = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await qc.invalidateQueries({ queryKey: ['dashboard-summary'] });
    setTimeout(() => {
      setIsRefreshing(false);
    }, 500);
  };

  const renderContent = () => {
    switch (currentPath) {
      case '/':
        return <OverviewPage onNavigate={setCurrentPath} />;
      case '/chat':
        return (
          <PlaceholderPage
            title="智能答疑会话 (CHAT)"
            phase="U2"
            description="基于 SSE 流式打字机响应、多轮会话树形管理与拍照 OCR 自动识题。"
            onBack={() => setCurrentPath('/')}
          />
        );
      case '/practice':
        return (
          <PlaceholderPage
            title="题库自测训练 (PRACTICE)"
            phase="U3"
            description="难度梯度出题、选项互锁交互与全自动 AI 批改解析。"
            onBack={() => setCurrentPath('/')}
          />
        );
      case '/review':
        return (
          <PlaceholderPage
            title="错题复习 (REVIEW)"
            phase="U4"
            description="艾宾浩斯抗遗忘时间轴、错因标签化归类与掌握度升级机制。"
            onBack={() => setCurrentPath('/')}
          />
        );
      case '/knowledge':
        return (
          <PlaceholderPage
            title="知识库文档 (KNOWLEDGE)"
            phase="U4"
            description="PDF 拖拽分块解析、SQLite 与向量分块双写检索与溯源查看。"
            onBack={() => setCurrentPath('/')}
          />
        );
      case '/code':
        return (
          <PlaceholderPage
            title="代码助教 (CODE)"
            phase="U5"
            description="Monaco 编辑器、沙箱安全隔离执行与多阶段 AI 渐进式启发。"
            onBack={() => setCurrentPath('/')}
          />
        );
      default:
        return <OverviewPage onNavigate={setCurrentPath} />;
    }
  };

  return (
    <AppShell
      currentPath={currentPath}
      onNavigate={setCurrentPath}
      onRefresh={handleRefresh}
      isRefreshing={isRefreshing}
    >
      {renderContent()}
    </AppShell>
  );
};

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
