export interface OverviewStats {
  session_count: number;
  message_count: number;
  document_count: number;
}

export interface MistakeStats {
  total: number;
  pending: number;
  confirmed: number;
  dismissed: number;
  due_today: number;
}

export interface MasteryDistribution {
  low: number;
  medium: number;
  high: number;
}

export interface MasteryStats {
  total_concepts: number;
  average_score: number;
  distribution: MasteryDistribution;
}

export interface RecentRun {
  id: string;
  session_id: string;
  prompt_preview: string;
  status: string;
  latency_ms: number;
  model: string;
  cost_yuan: number;
  created_at: string;
}

export interface LatestEvaluation {
  id: string;
  dataset_name: string;
  dataset_version: string;
  mode: string;
  status: string;
  sample_count: number;
  passed: number;
  pass_rate: number;
  summary: Record<string, any>;
  started_at: string;
  finished_at: string;
}

export interface DashboardSummaryResponse {
  user_id: string;
  generated_at: string;
  overview: OverviewStats;
  mistakes: MistakeStats;
  mastery: MasteryStats;
  recent_runs: RecentRun[];
  latest_evaluation: LatestEvaluation | null;
}
