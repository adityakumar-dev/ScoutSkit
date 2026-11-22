import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api } from "../api";

const IDEAS = [
  "Open the SIH website and give me every problem statement",
  "Find the B.Tech CSE syllabus on the uktech website",
  "Compare the top 5 laptops under ₹60,000 on two sites",
];

function hostOf(url: string): string {
  try {
    return new URL(url.includes("://") ? url : `https://${url}`).host;
  } catch {
    return "URL";
  }
}

/** The one place a mission starts: say what you want, optionally where to start and whether the whole web is allowed. */
export function Composer({ onStarted }: { onStarted: (id: string) => void }) {
  const [task, setTask] = useState("");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState("");
  const [web, setWeb] = useState(false);
  const [autonomous, setAutonomous] = useState(false);
  const [open, setOpen] = useState<"" | "url" | "provider">("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLTextAreaElement>(null);
  const ready = task.trim().length >= 3 && !busy;

  async function launch(event?: FormEvent) {
    event?.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError("");
    try {
      const { id } = await api.startRun({ task: task.trim(), url: url.trim() || undefined, provider: provider.trim() || undefined, strict: Boolean(provider.trim()), web, autonomous });
      setTask("");
      onStarted(id);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  const onKey = (event: KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      launch();
    }
  };

  return (
    <form className="composer" onSubmit={launch}>
      <textarea ref={box} value={task} onChange={(e) => setTask(e.target.value)} onKeyDown={onKey} rows={3} autoFocus
        placeholder="Describe a mission… e.g. get every problem statement from the SIH site" aria-label="Mission" />
      {open === "url" && <input className="composer-extra" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Start URL (optional) — https://…" inputMode="url" autoFocus />}
      {open === "provider" && <input className="composer-extra" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="Provider (optional) — e.g. nvidia_super" autoFocus />}
      <div className="composer-bar">
        <div className="chips">
          <button type="button" className={web ? "chip on" : "chip"} onClick={() => setWeb(!web)} title="May visit any public website; starts from a search when there is no URL">◍ Open web</button>
          <button type="button" className={url || open === "url" ? "chip on" : "chip"} onClick={() => setOpen(open === "url" ? "" : "url")}>⌁ {url ? hostOf(url) : "Start URL"}</button>
          <button type="button" className={autonomous ? "chip on" : "chip"} onClick={() => setAutonomous(!autonomous)} title="Start without waiting for you to approve the plan">⚡ {autonomous ? "Autonomous" : "Ask before acting"}</button>
          <button type="button" className={provider || open === "provider" ? "chip on" : "chip"} onClick={() => setOpen(open === "provider" ? "" : "provider")}>✦ {provider || "Model"}</button>
        </div>
        <button className="launch" disabled={!ready} aria-label="Launch">{busy ? <span className="spinner" /> : "↑"}</button>
      </div>
      {error && <p className="error">{error}</p>}
      {!task && (
        <div className="ideas">
          {IDEAS.map((idea) => (
            <button type="button" key={idea} onClick={() => { setTask(idea); box.current?.focus(); }}>{idea}</button>
          ))}
        </div>
      )}
    </form>
  );
}
