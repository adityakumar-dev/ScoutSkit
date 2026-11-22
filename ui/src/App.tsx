import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type RunSummary } from "./api";
import { CommandPalette, type Command } from "./components/CommandPalette";
import { Home } from "./components/Home";
import { MissionView } from "./components/MissionView";
import { useRunStream } from "./useRunStream";

const REFRESH_MS = 3000;

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const { run, frame, send } = useRunStream(selected);

  const refresh = useCallback(() => api.listRuns().then(setRuns).catch(() => undefined), []);
  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const open = useCallback((id: string) => { setSelected(id); refresh(); }, [refresh]);
  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [{ id: "new", label: "New mission", hint: "home", run: () => setSelected(null) }];
    if (selected && run.status === "running") {
      list.push({ id: "take", label: "Take over the browser", run: () => api.takeOver(selected, "user").catch(() => undefined) });
      list.push({ id: "stop", label: "Stop this mission", run: () => api.stopRun(selected).then(refresh) });
    }
    return list;
  }, [selected, run.status, refresh]);

  return (
    <div className="app">
      <div className="aurora" aria-hidden><i /><i /><i /></div>
      {selected ? (
        <MissionView runId={selected} task={runs.find((r) => r.id === selected)?.task ?? ""} run={run} frame={frame} send={send} onHome={() => setSelected(null)} onChanged={refresh} />
      ) : (
        <Home runs={runs} onOpen={open} />
      )}
      <CommandPalette runs={runs} commands={commands} onOpenRun={open} />
    </div>
  );
}
