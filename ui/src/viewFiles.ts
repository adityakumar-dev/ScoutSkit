// Everything a person can open in the viewer for one run: the files the agents saved, and the result tables.

import { api } from "./api";
import type { RunView } from "./runState";

export interface ViewFile {
  key: string;
  name: string;
  label: string; // what it is, for the list: "saved by Scout 1", "result table"
  url: string; // what the viewer loads
  downloadUrl: string;
  size?: number;
}

export function viewFiles(runId: string, run: RunView): ViewFile[] {
  const named = run.agents.length > 2;
  const saved: ViewFile[] = run.files.map((f) => ({
    key: `saved:${f.name}`,
    name: f.name,
    label: `saved${named ? ` by ${run.agents.find((a) => a.id === f.agent)?.name ?? f.agent}` : ""}`,
    url: api.savedUrl(runId, f.name),
    downloadUrl: `${api.savedUrl(runId, f.name)}?download=true`,
    size: f.size,
  }));
  const results: ViewFile[] =
    run.status !== "running" && run.items > 0
      ? ["result.csv", "result.json"].map((name) => ({ key: `result:${name}`, name, label: "result table", url: api.fileUrl(runId, name), downloadUrl: api.fileUrl(runId, name) }))
      : [];
  return [...saved, ...results];
}
