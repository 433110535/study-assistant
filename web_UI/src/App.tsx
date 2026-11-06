import React, { useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/Overview';
import { ChatPage } from './pages/Chat/ChatPage';
import { PracticePage } from './pages/Practice/PracticePage';
import { ReviewPage } from './pages/Review/ReviewPage';
import { KnowledgePage } from './pages/Knowledge/KnowledgePage';
import { CodePage } from './pages/Code/CodePage';


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
        return <ChatPage />;
      case '/practice':
        return <PracticePage onNavigate={setCurrentPath} />;
      case '/review':
        return <ReviewPage onNavigate={setCurrentPath} />;
      case '/knowledge':
        return <KnowledgePage onNavigate={setCurrentPath} />;
      case '/code':
        return <CodePage />;
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
