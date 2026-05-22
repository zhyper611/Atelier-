export type User = {
  id: string;
  username: string;
  created_at?: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type IntentType = "chat" | "search" | "image" | "video";

export type PlanningMode = "auto" | "always" | "off";

export type ToolResultType =
  | "search"
  | "fetch"
  | "image"
  | "video"
  | "calculation"
  | "code"
  | "document"
  | "analysis"
  | "knowledge";

export type KnowledgeCitation = {
  index: number;
  doc_id: string;
  filename: string;
  chunk_index: number;
  excerpt: string;
  score?: number | null;
};

export type KnowledgeDocument = {
  doc_id: string;
  filename: string;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
};

export type KnowledgeDocumentListResponse = {
  documents: KnowledgeDocument[];
};

export type IndexDocumentResponse = {
  doc_id: string;
  filename: string;
  chunk_count: number;
};

export type ToolResult = {
  type: ToolResultType;
  url?: string | null;
  content?: string | null;
  metadata?: Record<string, unknown>;
};

export type AttachmentRef = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
};

export type PlanStepStatus = "pending" | "in_progress" | "done";

export type TaskPlanStep = {
  id: string;
  title: string;
  description: string;
  status: PlanStepStatus;
};

export type TaskPlan = {
  goal: string;
  steps: TaskPlanStep[];
  created_at?: string;
};

export type ChatMessage = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_result?: ToolResult | null;
  run_id?: string | null;
  steps?: AgentStepSummary[];
  attachments?: AttachmentRef[];
  /** 仅前端：attachment id -> 本地 blob 预览（图片） */
  attachment_previews?: Record<string, string>;
  plan?: TaskPlan | null;
};

export type RequestOptions = {
  default_image_size: string;
  default_video_size: string;
  default_video_duration_seconds: number;
  planning_mode?: PlanningMode;
};

export type ChatRequest = {
  session_id: string;
  message: string;
  options: RequestOptions;
  attachments?: string[];
  enable_planning?: boolean | null;
  /** true=知识库向量检索；false=联网搜索 */
  use_knowledge_base?: boolean;
};

export type AgentStepSummary = {
  step: number;
  tool_name?: string | null;
  tool_input?: Record<string, unknown>;
  observation_preview?: string | null;
};

export type ChatResponse = {
  session_id: string;
  intent: IntentType;
  answer: string;
  run_id?: string;
  tool_result?: ToolResult | null;
  steps?: AgentStepSummary[];
  plan?: TaskPlan | null;
};

export type SessionHistoryResponse = {
  session_id: string;
  messages: ChatMessage[];
};

export type AttachmentUploadResponse = {
  attachments: AttachmentRef[];
};

export type SseEventName =
  | "run_started"
  | "plan_created"
  | "step_started"
  | "step_limit"
  | "tool_started"
  | "tool_result"
  | "delta"
  | "error"
  | "final";

export type SseEvent = {
  event: SseEventName;
  data: Record<string, unknown>;
};

export const DEFAULT_OPTIONS: RequestOptions = {
  default_image_size: "2048x2048",
  default_video_size: "1280x720",
  default_video_duration_seconds: 5,
  planning_mode: "auto",
};
