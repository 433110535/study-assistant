import React from 'react';
import { DashboardSummaryResponse } from '@/types/dashboard';
import { MessageSquareText, FileText, AlertTriangle, Award } from 'lucide-react';

interface MetricGridProps {
  data: DashboardSummaryResponse;
}

export const MetricGrid: React.FC<MetricGridProps> = ({ data }) => {
  const { overview, mistakes, mastery } = data;

  const dueTodayHighlight = mistakes.due_today > 0;
  const masteryPercentage = Math.round(mastery.average_score <= 1.0 ? mastery.average_score * 100 : mastery.average_score);

  const cards = [
    {
      id: 'sessions',
      title: 'TOTAL SESSIONS',
      subtitle: '历史答疑与练习会话',
      value: overview.session_count.toString(),
      subValue: `${overview.message_count} 条互动流水`,
      icon: MessageSquareText,
      highlight: false,
    },
    {
      id: 'documents',
      title: 'KNOWLEDGE BASE',
      subtitle: '已向量化核心文献',
      value: overview.document_count.toString(),
      subValue: '本地 SQLite + 向量分块',
      icon: FileText,
      highlight: false,
    },
    {
      id: 'due_today',
      title: 'DUE TODAY',
      subtitle: '今日艾宾浩斯复习',
      value: mistakes.due_today.toString(),
      subValue: dueTodayHighlight ? '需立即巩固错题' : '今日复习任务已达成',
      icon: AlertTriangle,
      highlight: dueTodayHighlight,
    },
    {
      id: 'mastery',
      title: 'MASTERY SCORE',
      subtitle: '全学科概念掌握度',
      value: `${masteryPercentage}%`,
      subValue: `覆盖 ${mastery.total_concepts} 个认知考点`,
      icon: Award,
      highlight: false,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.id}
            className={`flex flex-col justify-between p-4 md:p-5 rounded-sm bg-[#141414] border transition-colors ${
              card.highlight
                ? 'border-[#FAFF69] bg-[#141414]/90'
                : 'border-[rgba(65,65,65,0.8)] hover:border-[#FAFF69]/50'
            }`}
          >
            {/* 顶栏：标签与图标 */}
            <div className="flex items-center justify-between gap-2 mb-3">
              <span
                className={`text-[10px] md:text-[11px] font-bold font-mono tracking-label uppercase truncate ${
                  card.highlight ? 'text-[#FAFF69]' : 'text-[#A1A1AA]'
                }`}
              >
                {card.title}
              </span>
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  card.highlight ? 'text-[#FAFF69]' : 'text-[#71717A]'
                }`}
              />
            </div>

            {/* 中间：超大号数据核心 */}
            <div className="my-1">
              <div
                className={`font-mono font-black text-3xl md:text-5xl tracking-tight ${
                  card.highlight ? 'text-[#FAFF69]' : 'text-white'
                }`}
              >
                {card.value}
              </div>
            </div>

            {/* 底栏：细项说明 */}
            <div className="mt-3 pt-2 border-t border-[rgba(65,65,65,0.4)] flex flex-col gap-0.5">
              <span className="text-[11px] text-[#A1A1AA] truncate">
                {card.subtitle}
              </span>
              <span className="text-[10px] font-mono text-[#71717A] truncate">
                {card.subValue}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
