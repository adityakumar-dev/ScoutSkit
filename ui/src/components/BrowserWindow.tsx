import { useEffect, useState, type FormEvent } from "react";
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
    <div className={`window${driving ? " driving" : ""}${run.status === "running" ? "" : " ended"}`}>
      <div className="window-top">
        <span className="lights" aria-hidden><i /><i /><i /></span>
        <div className="tabs" role="tablist">
          {run.tabs.map((tab) => (
            <div key={tab.index} className={tab.active ? "tab active" : "tab"} role="tab" aria-selected={tab.active}>
              <button className="tab-title" disabled={!driving} onClick={() => send({ kind: "switch_tab", index: tab.index })} title={tab.url}>{titleOf(tab)}</button>
              {driving && run.tabs.length > 1 && <button className="tab-x" aria-label={`Close tab ${tab.index}`} onClick={() => send({ kind: "close_tab", index: tab.index })}>×</button>}
            </div>
          ))}
          {driving && <button className="tab-plus" title="Open a copy of this tab" onClick={() => send({ kind: "duplicate_tab" })}>+</button>}
        </div>
      </div>
      <form className="omnibox" onSubmit={go}>
        <button type="button" disabled={!driving} title="Back" onClick={() => send({ kind: "back" })}>←</button>
        <button type="button" disabled={!driving} title="Reload" onClick={() => send({ kind: "reload" })}>↻</button>
        <div className="url">
          <span className="lock" aria-hidden>{address.startsWith("https") ? "🔒" : "◌"}</span>
          <input value={address} disabled={!driving} aria-label="Address" onFocus={() => setEditing(true)} onBlur={() => setEditing(false)} onChange={(e) => setAddress(e.target.value)} />
        </div>
        {run.status === "running" ? (
          <button type="button" className={`who ${run.control}`} onClick={() => onControl(run.control === "agent" ? "user" : "agent")}
            title={run.control === "agent" ? "Pause the agent and use this browser yourself" : run.control === "requested" ? "Cancel the request" : "Give the browser back to the agent"}>
            {run.control === "agent" ? "✋ Take control" : run.control === "requested" ? "handing over… (cancel)" : "↩ Hand back"}
          </button>
        ) : <span className="who">finished</span>}
      </form>
      <LiveView runId={runId} run={run} frame={frame} screenshotUrl={screenshotUrl} send={send} />
    </div>
  );
}
