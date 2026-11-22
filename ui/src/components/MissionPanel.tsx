import type { RunView } from "../runState";
import { Activity } from "./Activity";
import { AgentGraph } from "./AgentGraph";
import { Files } from "./Files";
import { viewFiles } from "../viewFiles";
import { PlanPanel } from "./PlanPanel";
import { ResultTable } from "./ResultTable";

export const TABS = ["Plan", "Agents", "Activity", "Data"] as const;
export type PanelTab = (typeof TABS)[number];

export function MissionPanel({ runId, run, tab, setTab, onOpenFile }: { runId: string; run: RunView; tab: PanelTab; setTab: (tab: PanelTab) => void; onOpenFile: (key: string) => void }) {
  const count: Partial<Record<PanelTab, number>> = { Agents: run.agents.length - 1, Activity: run.steps.length, Data: run.items + run.files.length };
  return (
    <section className="panel">
      <nav className="segmented" style={{ ["--i" as string]: TABS.indexOf(tab) }}>
        <span className="seg-glider" aria-hidden />
        {TABS.map((name) => (
          <button key={name} className={name === tab ? "on" : ""} onClick={() => setTab(name)}>
            {name}{count[name] ? <sup>{count[name]}</sup> : null}
          </button>
        ))}
      </nav>
      <div className="panel-body">
        {tab === "Plan" && <PlanPanel run={run} />}
        {tab === "Agents" && <AgentGraph runId={runId} run={run} />}
        {tab === "Activity" && <Activity run={run} />}
        {tab === "Data" && (
          <>
            <Files files={viewFiles(runId, run)} onOpen={onOpenFile} />
            {run.status === "running" || !run.items
              ? <p className="hint">{run.status === "running" ? `${run.items} items collected so far; the table appears when the mission ends.` : run.files.length ? "" : "Nothing was collected."}</p>
              : <ResultTable runId={runId} items={run.items} hasRecipe={run.hasRecipe} onExpand={() => onOpenFile("result:result.csv")} />}
          </>
        )}
      </div>
    </section>
  );
}
