import { Activity as ActivityIcon, Database, ListChecks, Users } from "lucide-react";
import type { PanelTab } from "../settings";
import type { RunView } from "../runState";
import { viewFiles } from "../viewFiles";
import { Activity } from "./Activity";
import { AgentGraph } from "./AgentGraph";
import { Files } from "./Files";
import { PlanPanel } from "./PlanPanel";
import { ResultTable } from "./ResultTable";

const TABS: { name: PanelTab; icon: typeof Users }[] = [
  { name: "Plan", icon: ListChecks }, { name: "Agents", icon: Users }, { name: "Activity", icon: ActivityIcon }, { name: "Data", icon: Database },
];

interface Props {
  runId: string;
  run: RunView;
  tab: PanelTab;
  setTab: (tab: PanelTab) => void;
  onOpenFile: (key: string) => void;
}

export function Inspector({ runId, run, tab, setTab, onOpenFile }: Props) {
  const count: Partial<Record<PanelTab, number>> = { Agents: run.agents.length - 1, Activity: run.steps.length, Data: run.items + run.files.length };
  return (
    <section className="inspector" aria-label="Inspector">
      <nav className="tabs" role="tablist">
        {TABS.map(({ name, icon: Icon }) => (
          <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? "on" : ""} onClick={() => setTab(name)}>
            <Icon size={14} /> {name}{count[name] ? <span className="count">{count[name]}</span> : null}
          </button>
        ))}
      </nav>
      <div className="tab-body" role="tabpanel">
        {tab === "Plan" && <PlanPanel run={run} />}
        {tab === "Agents" && <AgentGraph runId={runId} run={run} />}
        {tab === "Activity" && <Activity run={run} />}
        {tab === "Data" && (
          <>
            <Files files={viewFiles(runId, run)} onOpen={onOpenFile} />
            {run.status === "running" || !run.items
              ? <p className="muted">{run.status === "running" ? `${run.items} items collected so far; the table appears when the run ends.` : run.files.length ? "" : "Nothing was collected."}</p>
              : <ResultTable runId={runId} items={run.items} hasRecipe={run.hasRecipe} onExpand={() => onOpenFile("result:result.csv")} />}
          </>
        )}
      </div>
    </section>
  );
}
