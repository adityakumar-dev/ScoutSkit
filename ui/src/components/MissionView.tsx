import { useState } from "react";
import { Hand, Square, Undo2 } from "lucide-react";
import { api } from "../api";
import type { RemoteInput } from "../remoteInput";
import { clock, phaseOf, PHASES, type RunView } from "../runState";
import { useSettings } from "../SettingsContext";
import { useResizable } from "../useResizable";
import { viewFiles } from "../viewFiles";
import { BrowserWindow } from "./BrowserWindow";
import { DownloadBubble } from "./DownloadBubble";
import { FileViewer } from "./FileViewer";
import { HelpToast } from "./HelpToast";
import { Inspector } from "./Inspector";
import { PlanCard } from "./PlanCard";
import { ResultCheckCard } from "./ResultCheckCard";
import { Status } from "./Status";

interface Props {
  runId: string;
  task: string;
  run: RunView;
  frame: string | null;
  send: (input: RemoteInput) => void;
  onChanged: () => void;
}

const PHASE_LABEL = { plan: "Plan", explore: "Explore", extract: "Extract", done: "Done" } as const;

/** One run: what it is and how far it got, the browser, and the inspector (plan, agents, activity, data). */
export function MissionView({ runId, task, run, frame, send, onChanged }: Props) {
  const { settings } = useSettings();
  const [error, setError] = useState("");
  const [tab, setTab] = useState(settings.startTab);
  const [viewing, setViewing] = useState<string | null>(null);
  const side = settings.panelSide;
  const { size, handle } = useResizable({ key: `inspector-${side}`, initial: side === "right" ? 400 : 300, min: side === "right" ? 280 : 160, max: side === "right" ? 760 : 560, axis: side === "right" ? "x" : "y", reverse: true });

  const running = run.status === "running";
  const phase = phaseOf(run);
  const latest = run.steps[run.steps.length - 1];
  const planning = running && !run.plan; // researching, or waiting for the person to approve
  const files = viewFiles(runId, run);
  const control = (mode: "user" | "agent") => {
    setError("");
    api.takeOver(runId, mode).catch((failure) => setError(failure instanceof Error ? failure.message : String(failure)));
  };
  const at = PHASES.indexOf(phase);

  return (
    <div className="mission">
      <header className="m-head">
        <div className="m-title">
          <h1 title={task}>{task || runId}</h1>
          <div className="m-stats">
            <Status status={run.status} />
            {run.approval === "waiting" && <span className="flag">Waiting for you</span>}
            <span className="mono">{clock(run.seconds)}</span>
            <span>{run.steps.length} steps</span>
            <span><b>{run.items}</b> items</span>
            {run.files.length > 0 && <button className="link" onClick={() => setTab("Data")}><b>{run.files.length}</b> files</button>}
            {run.agents.length > 2 && <span>{run.agents.filter((a) => a.status === "running" && a.id !== "main").length}/{run.agents.length - 1} scouts working</span>}
            {run.provider && <span className="mono muted">{run.provider}</span>}
          </div>
        </div>
        {running && (
          <div className="m-actions">
            {run.control === "agent" && !planning && <button className="btn" onClick={() => control("user")}><Hand size={15} /> Take control</button>}
            {run.control === "requested" && <button className="btn" onClick={() => control("agent")}>Cancel hand-over</button>}
            {run.control === "user" && <button className="btn primary" onClick={() => control("agent")}><Undo2 size={15} /> Hand back</button>}
            <button className="btn danger" onClick={() => api.stopRun(runId).then(onChanged)}><Square size={13} /> Stop</button>
          </div>
        )}
      </header>

      <ol className="stages" aria-label="Progress">
        {PHASES.map((name, index) => (
          <li key={name} className={index < at || (name === "done" && phase === "done") ? "past" : index === at ? "now" : ""} aria-current={index === at ? "step" : undefined}>
            <i className="dot" /><span>{PHASE_LABEL[name]}</span>
          </li>
        ))}
      </ol>

      {(run.message || run.inputNotice || error) && <p className={run.inputNotice || error ? "notice bad" : "notice"}>{run.inputNotice || error || run.message}</p>}
      {running && run.control === "user" && (
        <p className="notice info">You are driving; the agent is paused. Click, scroll, type and paste in the picture, or use the address bar and tabs. Password fields stay hidden from the agent; other text you type, it can read once you hand back.</p>
      )}
      <ResultCheckCard runId={runId} run={run} />

      <div className={`workspace side-${side}`} style={{ "--inspector": `${size}px` } as React.CSSProperties}>
        <section className="stage">
          {planning
            ? <PlanCard runId={runId} run={run} />
            : <BrowserWindow runId={runId} run={run} frame={frame} screenshotUrl={(shot) => api.screenshotUrl(runId, shot)} send={send} onControl={control} />}
          <HelpToast runId={runId} run={run} />
          <DownloadBubble files={run.files} live={running} onOpen={(name) => setViewing(`saved:${name}`)} onShowAll={() => setTab("Data")} />
        </section>
        <div className="split" {...handle} />
        <Inspector runId={runId} run={run} tab={tab} setTab={setTab} onOpenFile={setViewing} />
      </div>

      {settings.ticker && (
        <footer className="ticker">
          <i className={running ? "dot live" : "dot"} />
          {latest ? <><span className="mono">{latest.tool}</span><span className="ticker-text">{latest.detail || latest.outcome.split("\n")[0]}</span></> : <span className="ticker-text muted">{running ? "Starting…" : "No steps recorded."}</span>}
        </footer>
      )}
      {viewing && <FileViewer files={files} current={viewing} onChange={setViewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
