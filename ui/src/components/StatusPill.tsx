import type { RunStatus } from "../api";

const LABEL: Partial<Record<RunStatus, string>> = { max_steps: "step limit", max_budget: "budget used", running: "live" };

export function StatusPill({ status }: { status: RunStatus }) {
  return <span className={`pill ${status}`}>{status === "running" && <i className="pulse" />}{LABEL[status] ?? status}</span>;
}
