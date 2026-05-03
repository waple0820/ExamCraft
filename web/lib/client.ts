"use client";

import { backendUrl } from "@/lib/api";

export async function clientFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(backendUrl(path), {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

export async function clientLogin(username: string): Promise<{ id: string; username: string }> {
  const res = await clientFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `login failed: ${res.status}`);
  }
  return res.json();
}

export async function clientLogout(): Promise<void> {
  await clientFetch("/api/auth/logout", { method: "POST" });
}

export async function clientCreateBank(input: {
  name: string;
  description?: string;
}): Promise<{ id: string; name: string }> {
  const res = await clientFetch("/api/banks", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await res.text().catch(() => `create failed: ${res.status}`));
  return res.json();
}

export async function clientDeleteBank(id: string): Promise<void> {
  const res = await clientFetch(`/api/banks/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`delete failed: ${res.status}`);
}

export async function clientUploadSample(
  bankId: string,
  file: File,
): Promise<{ id: string; status: string }> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await fetch(backendUrl(`/api/banks/${bankId}/samples`), {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `upload failed: ${res.status}`);
  }
  return res.json();
}

export async function clientDeleteSample(sampleId: string): Promise<void> {
  const res = await clientFetch(`/api/samples/${sampleId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`delete failed: ${res.status}`);
}

export async function clientRefreshAnalysis(bankId: string): Promise<void> {
  const res = await clientFetch(`/api/banks/${bankId}/analysis/refresh`, {
    method: "POST",
  });
  if (!res.ok && res.status !== 202) {
    throw new Error(await res.text().catch(() => `refresh failed: ${res.status}`));
  }
}

export async function clientStartGeneration(
  bankId: string,
): Promise<{ id: string }> {
  const res = await clientFetch(`/api/banks/${bankId}/generations`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(await res.text().catch(() => `start failed: ${res.status}`));
  }
  return res.json();
}

export async function clientDeleteGeneration(jobId: string): Promise<void> {
  const res = await clientFetch(`/api/generations/${jobId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`delete failed: ${res.status}`);
  }
}

export async function clientPostChat(
  jobId: string,
  content: string,
): Promise<{ id: string; role: string; content: string; created_at: string }> {
  const res = await clientFetch(`/api/generations/${jobId}/chat`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
  if (!res.ok && res.status !== 202) {
    throw new Error(await res.text().catch(() => `chat failed: ${res.status}`));
  }
  return res.json();
}
