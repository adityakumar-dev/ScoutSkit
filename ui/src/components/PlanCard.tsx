import { useState } from "react";
import { ArrowRight, RefreshCw, TriangleAlert } from "lucide-react";
import { api } from "../api";
import type { RunView } from "../runState";
import { SourceItem } from "./SourceItem";

const host = (url: string) => url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];

/**
 * Before the browser opens: what the brain understood, the sources it picked from the search and why, and its steps.
 * The person continues, or adds context and gets a new plan.
 */
export function PlanCard({ runId, run }: { runId: string; run: RunView }) {
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { brief, approval } = run;

  const answer = async (action: "approve" | "revise") => {
    setBusy(true);
    setError("");
    try {
      await api.answer(runId, action, context.trim());
      setContext("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  if (!brief || approval === "revising") {
    return (
      <div className="plan-card researching">
        <div className="spinner" aria-hidden />
        <h3>{approval === "revising" ? "Re-planning with your context…" : "Researching…"}</h3>
        <p className="muted">Searching the web and Wikipedia, then picking the best sources. No browser is open yet.</p>
      </div>
    );
  }

  const others = brief.sources.filter((s) => !brief.picks.some((p) => p.url === s.url));
  return (
    <div className="plan-card">
      <div className="plan-card-head">
        <span className="eyebrow">Proposed plan{brief.context ? " (revised)" : ""}</span>
        <h3>{brief.understanding}</h3>
      </div>
      <div className="plan-card-cols">
        <section>
          <h4 className="section-h">Sources picked</h4>
          <ol className="sources">{brief.picks.map((pick, i) => <SourceItem key={pick.url} source={pick} rank={i + 1} />)}</ol>
          {others.length > 0 && (
            <details className="more-sources">
              <summary>{others.length} other results{brief.queries.length ? ` for ${brief.queries.map((q) => `“${q}”`).join(", ")}` : ""}</summary>
              <ul className="sources">{others.map((s) => <SourceItem key={s.url} source={s} />)}</ul>
            </details>
          )}
          {brief.notes.length > 0 && <p className="warn-note"><TriangleAlert size={13} /> {brief.notes.join(" · ")}</p>}
        </section>
        <section>
          <h4 className="section-h">Steps</h4>
          <ol className="steps">{brief.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
          {brief.agents > 1 && <p className="muted small">Sites the sub-agents start from: <span className="mono">{[...new Set(brief.picks.slice(0, brief.agents).map((p) => host(p.url)))].join(", ")}</span></p>}
          <p className="muted small">
            {brief.agents > 1
              ? <>{brief.agents} sub-agents explore picks 1–{brief.agents} in parallel; the first result the brain accepts wins and the others stop.</>
              : <>Starts at <span className="mono">{brief.startUrl}</span></>}
          </p>
          {brief.questions.length > 0 && (
            <div className="questions">
              <h4 className="section-h">Unsure about</h4>
              <ul>{brief.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </div>
          )}
        </section>
      </div>
      {approval === "waiting" && (
        <div className="plan-card-answer">
          <textarea value={context} onChange={(e) => setContext(e.target.value)} rows={2}
            placeholder="Add context or correct the plan — e.g. “only the CSE 2nd-year syllabus”, “the official site is uktech.ac.in”" />
          <div className="plan-card-buttons">
            {error && <span className="error">{error}</span>}
            <button className="btn" disabled={busy || !context.trim()} onClick={() => answer("revise")}><RefreshCw size={14} /> Re-plan with this</button>
            <button className="btn primary" disabled={busy} onClick={() => answer("approve")}>Continue <ArrowRight size={14} /></button>
          </div>
        </div>
      )}
    </div>
  );
}
