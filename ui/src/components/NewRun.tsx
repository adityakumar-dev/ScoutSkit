import { useState, type FormEvent } from "react";
import { ArrowUp, Globe, Link2 } from "lucide-react";
import { api } from "../api";
import { useSettings } from "../SettingsContext";
import { Segmented } from "./Segmented";

const EXAMPLES = [
  "Find all the SIH 2025 problem statements",
  "Download the B.Tech CSE syllabus from the uktech website",
  "Compare the five best-rated laptops under ₹60,000 on two shops",
];

/** The page for starting a run: what to do, where to start, how far it may roam, which model, whether to ask first. */
export function NewRun({ onStarted }: { onStarted: (id: string) => void }) {
  const { settings, update } = useSettings();
  const d = settings.runDefaults;
  const [task, setTask] = useState("");
  const [start, setStart] = useState<"search" | "site">("search");
  const [url, setUrl] = useState("");
  const [roam, setRoam] = useState<"site" | "web">(d.web ? "web" : "site");
  const [provider, setProvider] = useState(d.provider);
  const [autonomous, setAutonomous] = useState(d.autonomous);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = task.trim().length >= 3 && (start === "search" || url.trim().length > 3) && !busy;

  async function launch(event?: FormEvent) {
    event?.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError("");
    try {
      const withUrl = start === "site" ? (/^[a-z]+:\/\//i.test(url.trim()) ? url.trim() : `https://${url.trim()}`) : undefined;
      const { id } = await api.startRun({
        task: task.trim(), url: withUrl, provider: provider.trim() || undefined, strict: Boolean(provider.trim()),
        web: start === "search" || roam === "web", autonomous,
      });
      if (remember) update({ runDefaults: { autonomous, web: roam === "web", provider: provider.trim() } });
      setTask("");
      onStarted(id);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>New run</h1>
        <p className="muted">Describe the job. The agent researches first, shows you a plan, and only then opens a browser.</p>
      </header>
      <div className="new-run-grid">
        <form className="form" onSubmit={launch}>
          <div className="field">
            <label htmlFor="task">Task</label>
            <textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} rows={4} autoFocus placeholder="e.g. Collect every problem statement from the SIH 2025 list, with its organisation and theme"
              onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") launch(); }} />
          </div>

          <div className="field">
            <span className="label">Start from</span>
            <Segmented label="Where to start" value={start} onChange={setStart} options={[
              { value: "search", label: "Search the web", hint: "The agent searches for the right sites and shows you its picks" },
              { value: "site", label: "A specific site", hint: "You name the address" },
            ]} />
            {start === "site" ? (
              <div className="input-icon"><Link2 size={15} /><input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.org/page" inputMode="url" aria-label="Start address" /></div>
            ) : (
              <p className="hint"><Globe size={13} /> It may visit any public website the search finds. Private networks stay blocked.</p>
            )}
          </div>

          {start === "site" && (
            <div className="field">
              <span className="label">May visit</span>
              <Segmented label="Where it may go" value={roam} onChange={setRoam} options={[
                { value: "site", label: "Only this site" }, { value: "web", label: "Any public website" },
              ]} />
            </div>
          )}

          <div className="field">
            <span className="label">Before acting</span>
            <Segmented label="Plan approval" value={autonomous ? "auto" : "ask"} onChange={(v) => setAutonomous(v === "auto")} options={[
              { value: "ask", label: "Show me the plan first", hint: "You approve, or add context, before the browser opens" },
              { value: "auto", label: "Run on its own" },
            ]} />
          </div>

          <div className="field">
            <label htmlFor="model">Model <span className="muted">(optional)</span></label>
            <input id="model" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="Default from scoutskit.toml, or e.g. nvidia_super" />
          </div>

          <label className="check"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember these choices for next time</label>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="form-actions">
            <button className="btn primary" disabled={!ready}>{busy ? "Starting…" : <><ArrowUp size={15} /> Start run</>}</button>
            <span className="muted small">or press <kbd>Ctrl</kbd> <kbd>Enter</kbd></span>
          </div>
        </form>

        <aside className="examples">
          <h2>Examples</h2>
          <ul>
            {EXAMPLES.map((example) => (
              <li key={example}><button type="button" onClick={() => setTask(example)}>{example}</button></li>
            ))}
          </ul>
          <h2>How a run goes</h2>
          <ol className="how">
            <li><b>Research.</b> Searches the web and picks sources.</li>
            <li><b>Plan.</b> You approve it or add context.</li>
            <li><b>Explore.</b> Sub-agents work in their own browsers.</li>
            <li><b>Check.</b> The brain verifies; you accept.</li>
          </ol>
        </aside>
      </div>
    </div>
  );
}
