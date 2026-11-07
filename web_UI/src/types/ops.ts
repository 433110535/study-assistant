export interface TraceItem {
  id: string;
  trace_id?: string;
  session_id?: string;
  user_input_preview?: string;
  final_answer?: string;
  iterations: number;
  tools_used?: string;
  latency_ms?: number;
  status: string;
  created_at: string;
  model?: string;
  token_in?: number;
  token_out?: number;
  cost_yuan?: number;
}

export interface ToolCallItem {
  id: number;
  tool_name: string;
  args_json?: string;
  result_preview?: string;
  status?: string;
  latency_ms?: number;
  created_at: string;
}

export interface TraceDetailResponse {
  run: TraceItem;
  tool_calls: ToolCallItem[];
}

export interface TracesListResponse {
  traces: TraceItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalRunItem {
  id: string;
  dataset_name: string;
  dataset_version: string;
  mode: string;
  status: string;
  sample_count: number;
  passed: number;
  started_at: string;
  finished_at?: string;
  summary?: {
    accuracy: number;
    faithfulness?: number | null;
    passed: number;
    total: number;
    failure_attribution?: Record<string, number>;
  };
}

export interface EvalCompareResponse {
  base_run: {
    id: string;
    dataset_name: string;
    dataset_version: string;
    started_at: string;
    summary: {
      accuracy: number;
      faithfulness?: number | null;
      passed: number;
      total: number;
    };
  };
  target_run: {
    id: string;
    dataset_name: string;
    dataset_version: string;
    started_at: string;
    summary: {
      accuracy: number;
      faithfulness?: number | null;
      passed: number;
      total: number;
    };
  };
  delta: {
    accuracy_delta: number;
    passed_delta: number;
    faithfulness_delta?: number | null;
    sample_count_delta: number;
    regression_count: number;
    fixed_count: number;
  };
  regressions: string[];
  fixes: string[];
  samples: Array<{
    sample_id: string;
    status: string;
    base_passed?: boolean | null;
    target_passed?: boolean | null;
    base_detail?: string;
    target_detail?: string;
  }>;
}

export interface DatasetVersionItem {
  id: string;
  dataset_name: string;
  version: string;
  sample_count: number;
  content_hash: string;
  changelog: string;
  source_path?: string;
  created_at: string;
}
