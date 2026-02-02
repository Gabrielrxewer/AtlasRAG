export type Connection = {
  id: number;
  name: string;
  host: string;
  port: number;
  database: string;
  username: string;
  ssl_mode: string;
  created_at: string;
  updated_at: string;
};

export type Scan = {
  id: number;
  connection_id: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
};

export type Column = {
  id: number;
  table_id: number;
  name: string;
  data_type: string;
  is_nullable: boolean;
  default?: string | null;
  description?: string | null;
  annotations?: Record<string, unknown> | null;
};

export type TableSchema = {
  id: number;
  schema: string;
  name: string;
  table_type: string;
  description?: string | null;
  annotations?: Record<string, unknown> | null;
  columns: Column[];
};

export type Sample = {
  id: number;
  table_id: number;
  rows: Record<string, unknown>[];
  created_at: string;
};

export type ApiRoute = {
  id: number;
  name: string;
  base_url: string;
  path: string;
  method: string;
  headers_template?: Record<string, unknown> | null;
  auth_type: string;
  body_template?: Record<string, unknown> | null;
  query_params_template?: Record<string, unknown> | null;
  description?: string | null;
  tags?: string[] | null;
};

export type ApiRouteField = {
  location: string;
  name: string;
  data_type: string;
  description?: string | null;
  annotations?: Record<string, unknown> | null;
};

export type RagAnswer = {
  answer: string;
  citations: { item_type: string; item_id: number }[];
};

export type Agent = {
  id: number;
  name: string;
  role?: string | null;
  template?: string | null;
  model: string;
  base_prompt: string;
  rag_prompt?: string | null;
  enable_rag: boolean;
  allow_db: boolean;
  allow_apis: boolean;
  connection_ids: number[];
  api_route_ids: number[];
  created_at: string;
  updated_at: string;
};

export type AgentMessage = {
  id: number;
  agent_id: number;
  role: string;
  content: string;
  created_at: string;
};

export type AgentChatResponse = {
  message: AgentMessage;
  citations: { item_type: string; item_id: number }[];
};
