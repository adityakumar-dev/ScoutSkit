import { useState } from "react";
import { api } from "../api";
import type { RunView } from "../runState";

/** A sub-agent finished and the brain thinks it is complete: the person accepts it (the others stop) or lets the others keep looking. */
export function ResultCheckCard({ runId, run }: { runId: string; run: RunView }) {
  const [busy, setBusy] = useState(false);
  const check = run.resultCheck;
  if (!check || check.state !== "waiting" || run.status !== "running") return null;
  const others = run.agents.filter((a) => a.id !== "main" && a.id !== check.agent && a.status === "running").length;
  const answer = (action: "approve" | "revise") => {
    setBusy(true);
    api.answer(runId, action).finally(() => setBusy(false));
  };
  return (
    <div className="result-check" role="alertdialog" aria-label="Accept this result?">
      <span className="rc-icon">✓</span>
      <div className="rc-body">
        <strong>{check.name} finished: {check.items} items{check.files.length ? ` · ${check.files.length} file${check.files.length > 1 ? "s" : ""}` : ""}</strong>
        <span className="hint">Brain: {check.why}</span>
        {check.files.length > 0 && <span className="mono small">{check.files.join(", ")}</span>}
      </div>
      <div className="rc-actions">
        <button className="ghost" disabled={busy} onClick={() => answer("revise")}>{others ? `Keep looking (${others} still working)` : "Not right"}</button>
        <button className="primary" disabled={busy} onClick={() => answer("approve")}>{others ? "Accept & stop the others" : "Accept"}</button>
      </div>
    </div>
  );
}
