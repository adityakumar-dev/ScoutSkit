import type { RunView, StepView } from "../runState";

const ICONS: Record<string, string> = {
  goto: "↗", open_tab: "⧉", switch_tab: "⧉", close_tab: "⧉", list_tabs: "⧉", back: "←",
  click: "◉", hover: "◌", type: "⌨", press: "⌨", select: "▾", scroll: "↕", wait: "◷",
  find: "⌕", grep_source: "⌕", read_page: "☰", view_source: "</>", inspect_element: "◎", javascript_tool: "JS",
  run_python: "λ", save_file: "⤓", use_script_output: "⇣", extract_rows: "⇣", done: "✓",
};

function Step({ step, who }: { step: StepView; who: string }) {
  return (
    <li className={step.ok ? "act" : "act bad"}>
      <span className="act-icon" aria-hidden>{ICONS[step.tool] ?? "•"}</span>
      <div className="act-body">
        <div className="act-line">
          {who && <span className="act-who">{who}</span>}
          <span className="act-tool">{step.tool}</span>
          <span className="act-detail">{step.detail}</span>
          <span className="act-no">#{step.step}</span>
        </div>
        {step.outcome && (
          <details>
            <summary>{step.outcome.split("\n")[0].slice(0, 120)}</summary>
            <pre>{step.outcome.slice(0, 4000)}</pre>
          </details>
        )}
      </div>
    </li>
  );
}

/** What happened, newest first: every tool call with its result, and the run's notices. */
export function Activity({ run }: { run: RunView }) {
  if (!run.steps.length && !run.notices.length) return <p className="hint">Nothing yet.</p>;
  return (
    <>
      <ol className="activity">
        {[...run.steps].reverse().map((step, i) => <Step key={run.steps.length - i} step={step} who={run.agents.length > 2 ? step.agent.replace("a", "S") : ""} />)}
      </ol>
      {run.notices.length > 0 && (
        <details className="notices">
          <summary>{run.notices.length} notices</summary>
          <ul>{run.notices.map((notice, i) => <li key={i}>{notice}</li>)}</ul>
        </details>
      )}
    </>
  );
}
