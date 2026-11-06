export interface KnowledgeDocument {
  id?: string;
  doc_id?: string;
  title: string;
  subject: string;
  path?: string;
  chunks: number;
  created_at: string;
  user_id?: string;
  size_bytes?: number;
}

export interface KnowledgeStatsResponse {
  documents: KnowledgeDocument[];
  total_documents: number;
  total_chunks: number;
  stats: Record<string, any>;
  index_version: string;
}

export interface KnowledgeSearchResult {
  doc_id?: string;
  content: string;
  similarity?: number;
  score?: number;
  metadata: {
    title?: string;
    subject?: string;
    doc_id?: string;
    chunk_id?: number;
    [key: string]: any;
  };
}

export interface KnowledgeSearchResponse {
  results: KnowledgeSearchResult[];
  count: number;
}

export interface KnowledgeAskResponse {
  answer: string;
  sources: string[];
  results: KnowledgeSearchResult[];
  trace_id?: string;
}
