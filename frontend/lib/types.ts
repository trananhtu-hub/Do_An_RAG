export interface Me {
  id: string;
  email: string;
  is_admin: boolean;
}

export interface MetaOption {
  code: string;
  label: string;
  description?: string | null;
}

export interface AppMeta {
  models: MetaOption[];
  default_model: string;
  modes: MetaOption[];
  languages: MetaOption[];
  max_question_chars: number;
}

export interface ChatSession {
  id: string;
  title: string | null;
  message_count: number;
  token_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionList {
  items: ChatSession[];
  total: number;
}

export interface Citation {
  source: string;
  quote: string;
  document?: string | null;
  document_title?: string | null;
  section?: string | null;
  page?: number | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | string;
  content: string;
  rewritten_query: string | null;
  citations: Citation[];
  token_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  seq: number;
}

export interface MessageList {
  items: ChatMessage[];
  total: number;
}

export interface DocumentSummary {
  id: string;
  title: string;
  source_key: string | null;
  page_count: number | null;
}

export interface DocumentList {
  items: DocumentSummary[];
  total: number;
}

export interface QuizDomain {
  code: string;
  label: string;
  count: number;
}

export interface QuizDomains {
  items: QuizDomain[];
  total: number;
}

export interface QuizOption {
  label: string;
  text: string;
}

export interface QuizQuestion {
  id: string;
  question: string;
  domain: string | null;
  options: QuizOption[];
}

export interface QuizResultItem {
  question_id: string;
  question: string;
  domain: string | null;
  selected: string | null;
  correct_answer: string;
  is_correct: boolean;
  explanation: string | null;
  source: string | null;
}

export interface QuizSubmitResult {
  attempt_id: string;
  domain: string | null;
  total: number;
  correct: number;
  score: number;
  items: QuizResultItem[];
}

export interface QuizAttempt {
  id: string;
  domain: string | null;
  total: number;
  correct: number;
  score: number;
  created_at: string;
}

export interface QuizAttemptList {
  items: QuizAttempt[];
  total: number;
}

export interface AdminDailyPoint {
  day: string;
  queries: number;
  cost_usd: number;
  refusals: number;
  latency_p95_ms: number | null;
}

export interface AdminStats {
  period_days: number;
  totals: {
    questions: number;
    documents: number;
    chunks: number;
    sessions: number;
    queries: number;
    cost_usd: number;
    refusal_rate: number;
    error_rate: number;
    latency_p50_ms: number | null;
    latency_p95_ms: number | null;
    ttft_p95_ms: number | null;
  };
  daily: AdminDailyPoint[];
  generated_at: string;
}

export type AnswerMode = "fast" | "step_by_step";
export type AnswerLanguage = "vi" | "en";

export interface Preferences {
  mode: AnswerMode;
  language: AnswerLanguage;
  model: string;
}
