import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, Copy, Globe, Hand, Lock, RotateCw, Undo2, X } from "lucide-react";
import type { RemoteInput } from "../remoteInput";
import type { RunView, Tab } from "../runState";
import { LiveView } from "./LiveView";

interface Props {
  runId: string;
  run: RunView;
  frame: string | null;
  screenshotUrl: (shot: string) => string;
  send: (input: RemoteInput) => void;
  onControl: (mode: "user" | "agent") => void;
}

const titleOf = (tab: Tab) => tab.title || tab.url.replace(/^https?:\/\//, "") || "New tab";

/** The agent's browser, drawn as a browser: tabs, back/reload, address bar, copy tab. The controls work while a person drives. */
export function BrowserWindow({ runId, run, frame, screenshotUrl, send, onControl }: Props) {
  const driving = run.status === "running" && run.control === "user";
  const active = run.tabs.find((tab) => tab.active);
  const [address, setAddress] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setAddress(active?.url ?? run.plan?.startUrl ?? "");
  }, [active?.url, run.plan?.startUrl, editing]);

  const go = (event: FormEvent) => {
    event.preventDefault();
    const url = address.trim();
    if (url) send({ kind: "navigate", url: /^[a-z]+:\/\//i.test(url) ? url : `https://${url}` });
    setEditing(false);
  };

  return (
    <div className={`browser${driving ? " driving" : ""}${run.status === "running" ? "" : " ended"}`}>
      <div className="btabs" role="tablist">
        {run.tabs.map((tab) => (
          <div key={tab.index} className={tab.active ? "btab active" : "btab"} role="tab" aria-selected={tab.active}>
            <button className="btab-title" disabled={!driving} onClick={() => send({ kind: "switch_tab", index: tab.index })} title={tab.url}>{titleOf(tab)}</button>
            {driving && run.tabs.length > 1 && <button className="btab-x" aria-label={`Close tab ${tab.index}`} onClick={() => send({ kind: "close_tab", index: tab.index })}><X size={12} /></button>}
          </div>
        ))}
        {!run.tabs.length && <span className="muted small pad">no tabs yet</span>}
      </div>
      <form className="addr" onSubmit={go}>
        <button type="button" className="icon-btn" disabled={!driving} title="Back" aria-label="Back" onClick={() => send({ kind: "back" })}><ArrowLeft size={15} /></button>
        <button type="button" className="icon-btn" disabled={!driving} title="Reload" aria-label="Reload" onClick={() => send({ kind: "reload" })}><RotateCw size={14} /></button>
        <div className="url">
          {address.startsWith("https") ? <Lock size={12} /> : <Globe size={12} />}
          <input value={address} disabled={!driving} aria-label="Address" onFocus={() => setEditing(true)} onBlur={() => setEditing(false)} onChange={(e) => setAddress(e.target.value)} />
        </div>
        <button type="button" className="icon-btn" disabled={!driving || !active} title="Open a copy of this tab" aria-label="Duplicate tab" onClick={() => send({ kind: "duplicate_tab" })}><Copy size={14} /></button>
        {run.status === "running" ? (
          <button type="button" className={`driver ${run.control}`} onClick={() => onControl(run.control === "agent" ? "user" : "agent")}
            title={run.control === "agent" ? "Pause the agent and use this browser yourself" : run.control === "requested" ? "Cancel the request" : "Give the browser back to the agent"}>
            {run.control === "agent" ? <><Hand size={13} /> Take control</> : run.control === "requested" ? "Handing over… (cancel)" : <><Undo2 size={13} /> Hand back</>}
          </button>
        ) : <span className="driver idle">Finished</span>}
      </form>
      <LiveView runId={runId} run={run} frame={frame} screenshotUrl={screenshotUrl} send={send} />
    </div>
  );
}
