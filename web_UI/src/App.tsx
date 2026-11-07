import React, { useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/Overview';
import { ChatPage } from './pages/Chat/ChatPage';
import { PracticePage } from './pages/Practice/PracticePage';
import { ReviewPage } from './pages/Review/ReviewPage';
import { KnowledgePage } from './pages/Knowledge/KnowledgePage';
import { CodePage } from './pages/Code/CodePage';
import { OpsPage } from './pages/Ops/OpsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 秒缓存
      retry: 1,
    },
  },
});

function getInitialPath(): string {
  if (typeof window === 'undefined') return '/';
  const path = window.location.pathname;
  let stripped = path.replace(/^\/app(?:\/|$)/, '/');
  if (stripped.length > 1 && stripped.endsWith('/')) {
    stripped = stripped.slice(0, -1);
  }
  const valid = ['/', '/chat', '/practice', '/review', '/knowledge', '/code', '/ops'];
  const normalized = stripped.startsWith('/') ? stripped : '/' + stripped;
  return valid.includes(normalized) ? normalized : '/';
}

const AppContent: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>(getInitialPath);
  const qc = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  React.useEffect(() => {
    const onPopState = () => {
      setCurrentPath(getInitialPath());
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    if (typeof window !== 'undefined') {
      const isApp = window.location.pathname.startsWith('/app');
      const target = isApp ? (path === '/' ? '/app' : `/app${path}`) : path;
      if (window.location.pathname !== target) {
        window.history.pushState(null, '', target);
      }
    }
  };

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
        return <OverviewPage onNavigate={handleNavigate} />;
      case '/chat':
        return <ChatPage />;
      case '/practice':
        return <PracticePage onNavigate={handleNavigate} />;
      case '/review':
        return <ReviewPage onNavigate={handleNavigate} />;
      case '/knowledge':
        return <KnowledgePage onNavigate={handleNavigate} />;
      case '/code':
        return <CodePage />;
      case '/ops':
        return <OpsPage />;
      default:
        return <OverviewPage onNavigate={handleNavigate} />;
    }
  };

  return (
    <AppShell
      currentPath={currentPath}
      onNavigate={handleNavigate}
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
