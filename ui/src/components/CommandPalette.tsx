import { useEffect, useMemo, useState } from "react";
import type { RunSummary } from "../api";
import { StatusPill } from "./StatusPill";

export interface Command {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

/** Ctrl/⌘ K: jump to any mission or action by typing. */
export function CommandPalette({ runs, commands, onOpenRun }: { runs: RunSummary[]; commands: Command[]; onOpenRun: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
        setQuery("");
        setCursor(0);
      } else if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const items = useMemo(() => {
    const q = query.toLowerCase();
    const actions = commands.filter((c) => c.label.toLowerCase().includes(q)).map((c) => ({ key: c.id, label: c.label, hint: c.hint, run: c.run, status: undefined }));
    const missions = runs.filter((r) => (r.task || r.id).toLowerCase().includes(q)).slice(0, 8)
      .map((r) => ({ key: r.id, label: r.task || r.id, hint: `${r.items} items`, run: () => onOpenRun(r.id), status: r.status }));
    return [...actions, ...missions];
  }, [query, commands, runs, onOpenRun]);

  if (!open) return null;
  const choose = (index: number) => {
    items[index]?.run();
    setOpen(false);
  };
  return (
    <div className="palette-backdrop" onClick={() => setOpen(false)}>
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <input autoFocus value={query} placeholder="Search missions and actions…" onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            if (e.key === "Enter") choose(cursor);
          }} />
        <ul>
          {items.map((item, index) => (
            <li key={item.key} className={index === cursor ? "on" : ""} onMouseEnter={() => setCursor(index)} onClick={() => choose(index)}>
              <span className="palette-label">{item.label}</span>
              {item.status ? <StatusPill status={item.status} /> : null}
              {item.hint && <span className="hint">{item.hint}</span>}
            </li>
          ))}
          {!items.length && <li className="hint">No match.</li>}
        </ul>
      </div>
    </div>
  );
}
