import { useEffect, useMemo, useState } from "react";
import { CornerDownLeft } from "lucide-react";
import type { RunSummary } from "../api";
import { Status } from "./Status";

export interface Command {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

/** Ctrl/⌘ K: jump to any run or action by typing. */
export function CommandPalette({ open, onClose, runs, commands, onOpenRun }: { open: boolean; onClose: () => void; runs: RunSummary[]; commands: Command[]; onOpenRun: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  useEffect(() => { if (open) { setQuery(""); setCursor(0); } }, [open]);

  const items = useMemo(() => {
    const q = query.toLowerCase();
    const actions = commands.filter((c) => c.label.toLowerCase().includes(q)).map((c) => ({ key: c.id, group: "Actions", label: c.label, hint: c.hint, run: c.run, status: undefined as RunSummary["status"] | undefined }));
    const found = runs.filter((r) => (r.task || r.id).toLowerCase().includes(q)).slice(0, 8)
      .map((r) => ({ key: r.id, group: "Runs", label: r.task || r.id, hint: r.items ? `${r.items} items` : "", run: () => onOpenRun(r.id), status: r.status as RunSummary["status"] | undefined }));
    return [...actions, ...found];
  }, [query, commands, runs, onOpenRun]);

  if (!open) return null;
  const choose = (index: number) => { items[index]?.run(); onClose(); };
  return (
    <div className="scrim top" onClick={onClose}>
      <div className="palette" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={query} placeholder="Search runs and actions" onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            if (e.key === "Enter") choose(cursor);
          }} />
        <ul>
          {items.map((item, index) => (
            <li key={item.key} className={index === cursor ? "on" : ""} onMouseEnter={() => setCursor(index)} onClick={() => choose(index)}>
              {item.status ? <Status status={item.status} short /> : <span className="dot-gap" />}
              <span className="palette-label">{item.label}</span>
              {item.hint && <span className="muted small">{item.hint}</span>}
              {index === cursor && <CornerDownLeft size={13} className="muted" />}
            </li>
          ))}
          {!items.length && <li className="muted">Nothing matches.</li>}
        </ul>
      </div>
    </div>
  );
}
