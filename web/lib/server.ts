import { cookies } from "next/headers";

import {
  BACKEND,
  backendUrl,
  type Bank,
  type BankAnalysis,
  type ChatMessage,
  type Generation,
  type GenerationSummary,
  type Sample,
  type SampleDetail,
  type User,
} from "@/lib/api";

const SESSION_COOKIE = "examcraft_session";

async function authHeader(): Promise<HeadersInit> {
  const jar = await cookies();
  const value = jar.get(SESSION_COOKIE)?.value;
  return value ? { Cookie: `${SESSION_COOKIE}=${value}` } : {};
}

export async function serverFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = {
    ...(init.headers as Record<string, string> | undefined),
    ...(await authHeader()),
  };
  return fetch(backendUrl(path), {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function getMe(): Promise<User | null> {
  try {
    const res = await serverFetch("/api/auth/me");
    if (!res.ok) return null;
    return (await res.json()) as User;
  } catch {
    return null;
  }
}

export async function listBanks(): Promise<Bank[]> {
  const res = await serverFetch("/api/banks");
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as Bank[];
}

export async function getBank(id: string): Promise<Bank | null> {
  const res = await serverFetch(`/api/banks/${id}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as Bank;
}

export async function listSamples(bankId: string): Promise<Sample[]> {
  const res = await serverFetch(`/api/banks/${bankId}/samples`);
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as Sample[];
}

export async function getSample(sampleId: string): Promise<SampleDetail | null> {
  const res = await serverFetch(`/api/samples/${sampleId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as SampleDetail;
}

export async function getBankAnalysis(bankId: string): Promise<BankAnalysis> {
  const res = await serverFetch(`/api/banks/${bankId}/analysis`);
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as BankAnalysis;
}

export async function listGenerations(bankId: string): Promise<GenerationSummary[]> {
  const res = await serverFetch(`/api/banks/${bankId}/generations`);
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as GenerationSummary[];
}

export async function getGeneration(jobId: string): Promise<Generation | null> {
  const res = await serverFetch(`/api/generations/${jobId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as Generation;
}

export async function listChat(jobId: string): Promise<ChatMessage[]> {
  const res = await serverFetch(`/api/generations/${jobId}/chat`);
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ChatMessage[];
}

export { BACKEND };
