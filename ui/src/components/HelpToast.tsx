import { useState } from "react";
import { api } from "../api";
import type { RunView } from "../runState";

/** A sub-agent hit a CAPTCHA: the browser is the person's until they say it is done (or give up on the site). */
export function HelpToast({ runId, run }: { runId: string; run: RunView }) {
  const [busy, setBusy] = useState(false);
  const help = run.help;
  if (!help || run.status !== "running") return null;
  const ready = run.control === "user";
  const answer = (note: "" | "skip") => {
    setBusy(true);
    api.takeOver(runId, "agent", note).finally(() => setBusy(false));
  };
  const who = run.agents.length > 2 ? run.agents.find((a) => a.id === help.agent)?.name : "";
  return (
    <div className="help-toast" role="alertdialog" aria-label="Human help needed">
      <div className="help-head"><span className="help-icon">✋</span><strong>Human needed</strong><span className="pulse" /></div>
      <p>{who ? `${who}: ` : ""}<span className="mono">{help.host}</span> is asking you to prove you are human.</p>
      <p className="hint">
        {ready
          ? "The browser is yours: tick the box or solve the puzzle in the picture, then continue. The agent stays paused until you do. If you see no check, just continue."
          : "Handing the browser over as soon as the agent finishes its step…"}
      </p>
      {help.url && <p className="mono small dim" title={help.url}>{help.url.length > 70 ? `${help.url.slice(0, 70)}…` : help.url}</p>}
      <div className="help-actions">
        <button className="ghost" disabled={busy} onClick={() => answer("skip")}>Skip this site</button>
        <button className="primary" disabled={busy || !ready} onClick={() => answer("")}>I solved it — continue</button>
      </div>
    </div>
  );
}
