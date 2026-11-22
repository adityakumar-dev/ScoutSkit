import type { RunStatus } from "../api";

const LABEL: Record<RunStatus, string> = {
  running: "Running", completed: "Completed", incomplete: "Incomplete", failed: "Failed", max_steps: "Step limit", max_budget: "Budget used",
  cancelled: "Stopped", replayed: "Replayed", changed: "Changed", diverged: "Diverged", interrupted: "Interrupted", unknown: "Unknown",
};
const TONE: Record<RunStatus, string> = {
  running: "live", completed: "ok", replayed: "ok", failed: "bad", diverged: "bad", incomplete: "warn", max_steps: "warn", max_budget: "warn",
  changed: "warn", cancelled: "idle", interrupted: "idle", unknown: "idle",
};

/** A status as a dot and a word. */
export function Status({ status, short }: { status: RunStatus; short?: boolean }) {
  return (
    <span className={`status ${TONE[status] ?? "idle"}`}>
      <i className="dot" aria-hidden />
      {!short && LABEL[status]}
    </span>
  );
}
