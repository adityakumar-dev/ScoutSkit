import { useState } from "react";
import { api } from "../api";
import type { RemoteInput } from "../remoteInput";
import { clock, phaseOf, PHASES, type RunView } from "../runState";
import { BrowserWindow } from "./BrowserWindow";
import { viewFiles } from "../viewFiles";
import { DownloadBubble } from "./DownloadBubble";
import { HelpToast } from "./HelpToast";
import { FileViewer } from "./FileViewer";
import { MissionPanel, type PanelTab } from "./MissionPanel";
import { ResultCheckCard } from "./ResultCheckCard";
import { PlanCard } from "./PlanCard";
import { StatusPill } from "./StatusPill";

interface Props {
  runId: string;
  task: string;
  run: RunView;
  frame: string | null;
  send: (input: RemoteInput) => void;
  onHome: () => void;
  onChanged: () => void;
}

/** One mission: progress across the top, the browser on the left, plan/agents/activity/data on the right. */
export function MissionView({ runId, task, run, frame, send, onHome, onChanged }: Props) {
  const [error, setError] = useState("");
  const [tab, setTab] = useState<PanelTab>("Activity");
  const [viewing, setViewing] = useState<string | null>(null);
  const files = viewFiles(runId, run);
  const running = run.status === "running";
  const phase = phaseOf(run);
  const latest = run.steps[run.steps.length - 1];
  const planning = running && !run.plan; // researching, or waiting for the person to approve
  const control = (mode: "user" | "agent") => {
    setError("");
    api.takeOver(runId, mode).catch((failure) => setError(failure instanceof Error ? failure.message : String(failure)));
  };

  return (
    <div className="mission">
      <header className="topbar">
        <button className="ghost home-btn" onClick={onHome} title="All missions">◆</button>
        <div className="topbar-title">
          <h2 title={task}>{task || runId}</h2>
          <div className="stats">
            <StatusPill status={run.status} />
            {run.approval === "waiting" && <span className="pill waiting">waiting for you</span>}
            <span className="mono">{clock(run.seconds)}</span>
            <span>{run.steps.length} steps</span>
            <span><b>{run.items}</b> items</span>
            {run.files.length > 0 && <button className="linkish" onClick={() => setTab("Data")}><b>{run.files.length}</b> files</button>}
            {run.agents.length > 2 && <span>{run.agents.filter((a) => a.status === "running" && a.id !== "main").length}/{run.agents.length - 1} scouts working</span>}
            {run.provider && <span className="mono dim">{run.provider}</span>}
          </div>
        </div>
        {running && (
          <div className="actions">
            {run.control === "agent" && !planning && <button className="ghost" onClick={() => control("user")}>✋ Take over</button>}
            {run.control === "requested" && <button className="ghost" onClick={() => control("agent")}>Cancel take-over</button>}
            {run.control === "user" && <button className="primary" onClick={() => control("agent")}>Hand back to agent</button>}
            <button className="danger" onClick={() => api.stopRun(runId).then(onChanged)}>■ Stop</button>
          </div>
        )}
      </header>

      <ol className="phases">
        {PHASES.map((name, index) => {
          const at = PHASES.indexOf(phase);
          return <li key={name} className={index < at || (name === "done" && phase === "done") ? "past" : index === at ? "now" : ""}><span>{name}</span></li>;
        })}
      </ol>

      {(run.message || run.inputNotice || error) && <p className={run.inputNotice || error ? "flash bad" : "flash"}>{run.inputNotice || error || run.message}</p>}
      {running && run.control === "user" && (
        <p className="flash info">You are driving; the agent is paused. Click, scroll and type in the picture, or use the address bar and tabs. Password fields stay hidden from the agent; other text you type, it can read once you hand back.</p>
      )}

      <ResultCheckCard runId={runId} run={run} />

      <div className="mission-grid">
        {planning ? <PlanCard runId={runId} run={run} /> : <BrowserWindow runId={runId} run={run} frame={frame} screenshotUrl={(shot) => api.screenshotUrl(runId, shot)} send={send} onControl={control} />}
        <HelpToast runId={runId} run={run} />
        <MissionPanel runId={runId} run={run} tab={tab} setTab={setTab} onOpenFile={setViewing} />
        <DownloadBubble files={run.files} live={running} onOpen={(name) => setViewing(`saved:${name}`)} onShowAll={() => setTab("Data")} />
      </div>

      {viewing && <FileViewer files={files} current={viewing} onChange={setViewing} onClose={() => setViewing(null)} />}

      <footer className="ticker">
        <span className={running ? "beacon on" : "beacon"} />
        {latest ? <><span className="mono">{latest.tool}</span><span className="ticker-text">{latest.detail || latest.outcome.split("\n")[0]}</span></> : <span className="ticker-text">{running ? "Warming up…" : "No steps recorded."}</span>}
      </footer>
    </div>
  );
}
