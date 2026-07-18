export type User = {
  user_id: string;
  organization_id: string | null;
  email: string;
  full_name: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Project = {
  project_id: string;
  organization_id: string | null;
  name: string;
  collection: string;
  qdrant_collection: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type Document = {
  document_id: string;
  project_id: string;
  current_version_id: string | null;
  filename: string | null;
  source_type: string | null;
  mime_type: string | null;
  extension: string | null;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type DocumentVersion = {
  document_version_id: string;
  document_id: string;
  version_number: number;
  content_hash: string;
  bronze_path: string | null;
  silver_path: string | null;
  gold_path: string | null;
  parser_name: string | null;
  chunker_id: string | null;
  embedding_model: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
};

export type IngestionRun = {
  ingestion_run_id: string;
  document_id: string;
  document_version_id: string;
  status: IngestionStatus;
  airflow_dag_run_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: {
    bronze: boolean;
    silver: boolean;
    gold: boolean;
    qdrant: boolean;
  };
};

export type IngestionStatus =
  | "landed"
  | "queued"
  | "running"
  | "silver_completed"
  | "gold_completed"
  | "indexed"
  | "failed"
  | "cancelled";

export type Chunker = {
  id: string;
  name: string;
  tier: string;
  status: string;
  is_beta: boolean;
  short_description: string;
  long_description: string;
  best_for: string[];
  speed_level: string;
  quality_level: string;
  cost_level: string;
  default: boolean;
};

export type QueryHistoryItem = {
  query_log_id: string;
  project_id: string;
  question: string;
  answer: string | null;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  cache_hit: boolean;
  route: string | null;
  created_at: string;
};

export type RetrievalTrace = {
  retrieval_log_id: string;
  chunk_id: string | null;
  document_id: string | null;
  document_name: string | null;
  document_version_id: string | null;
  chunk_index: number | null;
  text: string | null;
  section_title: string | null;
  page_start: number | null;
  page_end: number | null;
  qdrant_score: number | null;
  rerank_score: number | null;
  rank: number;
  retrieval_strategy: string | null;
  used_in_answer: boolean;
};

export type QueryTrace = QueryHistoryItem & {
  retrievals: RetrievalTrace[];
};

export type StreamEvent = {
  id?: string;
  event: string;
  sequence?: number;
  timestamp?: string;
  [key: string]: unknown;
};
