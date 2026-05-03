export const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export const backendUrl = (path: string): string =>
  `${BACKEND}${path.startsWith("/") ? path : `/${path}`}`;

export type Health = {
  status: string;
  version: string;
  model: string;
  image_model: string;
};

export type User = { id: string; username: string };

export type Bank = {
  id: string;
  name: string;
  description: string | null;
  analysis_status: "idle" | "running" | "done" | "error";
  created_at: string;
};

export type SampleStatus =
  | "uploaded"
  | "extracting"
  | "analyzing"
  | "done"
  | "error";

export type Sample = {
  id: string;
  bank_id: string;
  original_filename: string;
  page_count: number;
  status: SampleStatus;
  error: string | null;
  created_at: string;
};

export type SamplePage = {
  id: string;
  page_number: number;
  image_url: string;
  has_analysis: boolean;
};

export type SampleDetail = Sample & { pages: SamplePage[] };

export type BankAnalysis = {
  status: "idle" | "running" | "done" | "error";
  error: string | null;
  analysis: Record<string, unknown> | null;
  sample_count: number;
  samples_done: number;
};

export type GenerationStatus = "queued" | "running" | "done" | "failed";

export type GeneratedPage = {
  page_number: number;
  status: "queued" | "done" | "error";
  image_url: string | null;
  error: string | null;
};

export type ExamSpec = {
  title?: string;
  meta?: Record<string, unknown>;
  sections?: Array<{
    name?: string;
    instructions?: string;
    problems?: Array<{
      id: number;
      type: string;
      content: string;
      choices?: string[];
      answer: string;
      knowledge_point?: string;
      difficulty?: number;
      points?: number;
    }>;
  }>;
};

export type Generation = {
  id: string;
  bank_id: string;
  status: GenerationStatus;
  progress_pct: number;
  current_step: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  spec: ExamSpec | null;
  pages: GeneratedPage[];
};

export type GenerationSummary = {
  id: string;
  bank_id: string;
  status: GenerationStatus;
  progress_pct: number;
  created_at: string;
  finished_at: string | null;
  page_count: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
