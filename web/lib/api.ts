// Client-side base URL for API calls. Empty string = same-origin / relative
// paths, which lets a tunnel on :3000 (cpolar / ngrok / cloudflared) cover
// the API too via the next.config.ts rewrite. In a split deploy (Vercel +
// Fly) point this at the public backend host.
const RAW = process.env.NEXT_PUBLIC_BACKEND_URL;
export const BACKEND = RAW === undefined ? "http://localhost:8000" : RAW;

export const backendUrl = (path: string): string => {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return BACKEND ? `${BACKEND}${suffix}` : suffix;
};

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

export type FigureStatus = "queued" | "done" | "error";

export type ProblemFigure =
  | { needed: false; description?: string }
  | {
      needed: true;
      description: string;
      status?: FigureStatus;
      error?: string | null;
      image_url?: string | null;
    };

export type ExamProblem = {
  id: number;
  type: string;
  content: string;
  choices?: string[];
  answer: string;
  knowledge_point?: string;
  difficulty?: number;
  points?: number;
  figure?: ProblemFigure;
};

export type ExamSpec = {
  title?: string;
  meta?: Record<string, unknown>;
  sections?: Array<{
    name?: string;
    instructions?: string;
    problems?: ExamProblem[];
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
};

export type GenerationSummary = {
  id: string;
  bank_id: string;
  status: GenerationStatus;
  progress_pct: number;
  created_at: string;
  finished_at: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
