import type { RunView } from "../runState";
import { SourceItem } from "./SourceItem";

const ICON = { todo: "○", doing: "◐", done: "●", skipped: "–" } as const;

/** What the agent set out to do. The to-do list appears when the planner writes one; until then, the goal and the starting point. */
export function PlanPanel({ run }: { run: RunView }) {
  const { plan, todo } = run;
  if (!plan) return <div className="skeleton-stack"><div /><div /><div /><p className="hint">{run.status === "running" ? "Planning…" : "This run has no recorded plan."}</p></div>;
  return (
    <div className="plan">
      <p className="goal">{plan.goal}</p>
      <div className="facts">
        <div><span>Start</span><a href={plan.startUrl} target="_blank" rel="noreferrer">{plan.startUrl.replace(/^https?:\/\//, "")}</a></div>
        <div><span>Collect</span><b>{plan.item || "—"}</b></div>
        <div><span>Fields</span><b>{plan.fields.length ? plan.fields.join(", ") : "as the page shows"}</b></div>
        <div><span>Expect</span><b>{plan.minItems > 1 ? `≥ ${plan.minItems}` : "any"}</b></div>
      </div>
      {run.brief && run.brief.picks.length > 0 && (
        <>
          <h4 className="panel-h">Sources picked</h4>
          <ol className="sources compact">{run.brief.picks.map((pick, i) => <SourceItem key={pick.url} source={pick} rank={i + 1} />)}</ol>
          <h4 className="panel-h">Steps</h4>
        </>
      )}
      {todo.length > 0 ? (
        <ol className="todo">
          {todo.map((item, index) => <li key={index} className={item.status}><span aria-hidden>{ICON[item.status]}</span>{item.text}</li>)}
        </ol>
      ) : (
        <p className="hint">The step-by-step to-do list will show here once the planner writes one.</p>
      )}
    </div>
  );
}
