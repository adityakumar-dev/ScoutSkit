import { ArrowUpRight, ChevronsUpDown, Code2, Copy, Download, Eye, FileSearch, Keyboard, MousePointerClick, ScrollText, Search, Check, Circle, type LucideIcon } from "lucide-react";
import type { RunView, StepView } from "../runState";

const ICONS: Record<string, LucideIcon> = {
  goto: ArrowUpRight, open_tab: Copy, switch_tab: Copy, close_tab: Copy, list_tabs: Copy, back: ArrowUpRight,
  click: MousePointerClick, hover: MousePointerClick, type: Keyboard, fill: Keyboard, press: Keyboard, select: MousePointerClick, scroll: ChevronsUpDown, wait_for: Eye,
  find: Search, grep_source: FileSearch, web_search: Search, find_items: Search, network_log: FileSearch, network_body: FileSearch, read_page: ScrollText, view_source: ScrollText,
  inspect_element: Eye, javascript_tool: Code2, run_python: Code2, use_script_output: Download, extract_rows: Download, save_file: Download, done: Check,
};

function Step({ step, who }: { step: StepView; who: string }) {
  const Icon = ICONS[step.tool] ?? Circle;
  return (
    <li className={step.ok ? "act" : "act bad"}>
      <span className="act-icon" aria-hidden><Icon size={13} /></span>
      <div className="act-body">
        <div className="act-line">
          {who && <span className="act-who mono">{who}</span>}
          <span className="act-tool mono">{step.tool}</span>
          <span className="act-detail">{step.detail}</span>
          <span className="act-no mono">{step.step}</span>
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
  if (!run.steps.length && !run.notices.length) return <p className="muted">Nothing yet.</p>;
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
