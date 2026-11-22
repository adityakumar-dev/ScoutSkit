// What the server sends and accepts. Mirrors src/scoutskit/server/app.py.

export type RunStatus = "running" | "completed" | "incomplete" | "failed" | "max_steps" | "max_budget" | "cancelled" | "replayed" | "changed" | "diverged" | "interrupted" | "unknown";

/** Who drives the browser: the agent, a person who asked and is waiting for the agent to finish its step, or the person. */
export type Control = "agent" | "requested" | "user";

export interface RunSummary {
  id: string;
  task: string;
  status: RunStatus;
  items: number;
  has_recipe: boolean;
  files?: string[];
}

export interface StartRequest {
  task: string;
  url?: string;
  provider?: string;
  strict?: boolean;
  web?: boolean; // may visit any public website
  autonomous?: boolean; // follow the plan without waiting for approval
}

/** One entry of the run's log, as the server streams it. `type` is "step" for tool calls. */
export interface RunEvent {
  type: string;
  [key: string]: unknown;
}

export type Row = Record<string, string>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const detail = await response.json().then((body) => body.detail).catch(() => response.statusText);
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => request<RunSummary[]>("/api/runs"),
  startRun: (body: StartRequest) =>
    request<{ id: string }>("/api/runs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }),
  takeOver: (id: string, mode: "user" | "agent", note: "" | "skip" = "") =>
    request<{ mode: Control }>(`/api/runs/${id}/control`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ mode, note }) }),
  answer: (id: string, action: "approve" | "revise", context = "") =>
    request<{ ok: boolean }>(`/api/runs/${id}/answer`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action, context }) }),
  focus: (id: string, agent: string) =>
    request<{ agent: string }>(`/api/runs/${id}/focus`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ agent }) }),
  savedUrl: (id: string, name: string) => `/api/runs/${id}/saved/${encodeURIComponent(name)}`,
  stopRun: (id: string) => request<{ stopped: boolean }>(`/api/runs/${id}/stop`, { method: "POST" }),
  rows: async (id: string): Promise<Row[]> => (await request<{ rows: Row[] }>(`/api/runs/${id}/files/result.json`)).rows,
  fileUrl: (id: string, name: string) => `/api/runs/${id}/files/${name}`,
  screenshotUrl: (id: string, name: string) => `/api/runs/${id}/${name}`,
  streamUrl: (id: string) => `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/runs/${id}/stream`,
};
