import { CheckCircle2, Circle, CircleDot, Minus } from "lucide-react";
import type { RunView } from "../runState";
import { SourceItem } from "./SourceItem";

const ICON = { todo: Circle, doing: CircleDot, done: CheckCircle2, skipped: Minus } as const;

/** What the agent set out to do. The to-do list appears when the planner writes one; until then, the goal and the starting point. */
export function PlanPanel({ run }: { run: RunView }) {
  const { plan, todo } = run;
  if (!plan) return <div className="skeleton-stack"><div /><div /><div /><p className="muted">{run.status === "running" ? "Planning…" : "This run has no recorded plan."}</p></div>;
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
          <h4 className="section-h">Sources picked</h4>
          <ol className="sources compact">{run.brief.picks.map((pick, i) => <SourceItem key={pick.url} source={pick} rank={i + 1} />)}</ol>
          <h4 className="section-h">Steps</h4>
        </>
      )}
      {todo.length > 0 ? (
        <ol className="todo-list">
          {todo.map((item, index) => {
            const Icon = ICON[item.status];
            return <li key={index} className={item.status}><Icon size={14} aria-hidden /><span>{item.text}</span></li>;
          })}
        </ol>
      ) : (
        <p className="muted">The step-by-step to-do list will show here once the planner writes one.</p>
      )}
    </div>
  );
}
