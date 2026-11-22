import { PanelLeftClose, PanelLeftOpen, Plus, Search, Settings as Cog } from "lucide-react";
import type { RunSummary } from "../api";
import { Status } from "./Status";

interface Props {
  runs: RunSummary[];
  selected: string | null;
  collapsed: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onSettings: () => void;
  onSearch: () => void;
}

const when = (id: string) => (/^\d{8}-\d{6}/.test(id) ? `${id.slice(9, 11)}:${id.slice(11, 13)}` : "");
const day = (id: string) => (/^\d{8}/.test(id) ? `${id.slice(6, 8)}/${id.slice(4, 6)}` : "");

/** Your runs, newest first: running ones on top, the rest grouped by day. */
export function Sidebar({ runs, selected, collapsed, onToggle, onSelect, onNew, onSettings, onSearch }: Props) {
  const live = runs.filter((r) => r.status === "running");
  const past = runs.filter((r) => r.status !== "running");
  const days = [...new Set(past.map((r) => day(r.id)))];

  const item = (run: RunSummary) => (
    <li key={run.id}>
      <button className={run.id === selected ? "run-item active" : "run-item"} onClick={() => onSelect(run.id)} title={run.task || run.id}>
        <Status status={run.status} short />
        <span className="run-task">{run.task || "Untitled run"}</span>
        <span className="run-meta">{run.items ? `${run.items}` : ""}{run.files?.length ? ` +${run.files.length}f` : ""}</span>
        <span className="run-time mono">{when(run.id)}</span>
      </button>
    </li>
  );

  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"}>
      <div className="brand">
        <span className="wordmark">{collapsed ? "SK" : "ScoutsKit"}</span>
        <button className="icon-btn" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>
      <button className="btn primary new-run" onClick={onNew} title="New run">
        <Plus size={15} />{!collapsed && "New run"}
      </button>
      {!collapsed && (
        <button className="search-btn" onClick={onSearch}>
          <Search size={14} /><span>Search</span><kbd>Ctrl K</kbd>
        </button>
      )}
      {!collapsed && (
        <nav className="run-groups" aria-label="Runs">
          {live.length > 0 && (<section><h3>Running</h3><ul>{live.map(item)}</ul></section>)}
          {days.map((d) => (<section key={d}><h3>{d}</h3><ul>{past.filter((r) => day(r.id) === d).map(item)}</ul></section>))}
          {!runs.length && <p className="muted pad">No runs yet.</p>}
        </nav>
      )}
      <div className="sidebar-foot">
        <button className="icon-btn" onClick={onSettings} aria-label="Settings" title="Settings"><Cog size={16} /></button>
        {!collapsed && <span className="muted small">{runs.length} {runs.length === 1 ? "run" : "runs"}</span>}
      </div>
    </aside>
  );
}
