import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type RunSummary } from "./api";
import { CommandPalette, type Command } from "./components/CommandPalette";
import { MissionView } from "./components/MissionView";
import { NewRun } from "./components/NewRun";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { Sidebar } from "./components/Sidebar";
import { SettingsProvider } from "./SettingsContext";
import { useRunStream } from "./useRunStream";

const REFRESH_MS = 3000;
const RUN_HASH = /^#\/run\/(\d{8}-\d{6}(?:-\d+)?)$/;

/** The run named by the address (#/run/<id>), so a reload or the back button keeps your place. */
export const runFromHash = (hash: string): string | null => RUN_HASH.exec(hash)?.[1] ?? null;
export const hashFor = (id: string | null): string => (id ? `#/run/${id}` : "#/");
const COLLAPSED_KEY = "scoutskit.sidebar.collapsed";

function Workbench() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelectedState] = useState<string | null>(() => runFromHash(location.hash));
  const setSelected = useCallback((id: string | null) => {
    setSelectedState(id);
    if (location.hash !== hashFor(id)) location.hash = hashFor(id);
  }, []);
  useEffect(() => {
    const onHash = () => setSelectedState(runFromHash(location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSED_KEY) === "1");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { run, frame, send } = useRunStream(selected);

  const refresh = useCallback(() => api.listRuns().then(setRuns).catch(() => undefined), []);
  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    try { localStorage.setItem(COLLAPSED_KEY, collapsed ? "1" : "0"); } catch { /* not remembered */ }
  }, [collapsed]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen((open) => !open); }
      else if (event.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const open = useCallback((id: string) => { setSelected(id); refresh(); }, [refresh, setSelected]);
  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [
      { id: "new", label: "New run", hint: "N", run: () => setSelected(null) },
      { id: "settings", label: "Open settings", run: () => setSettingsOpen(true) },
      { id: "sidebar", label: collapsed ? "Expand sidebar" : "Collapse sidebar", run: () => setCollapsed((c) => !c) },
    ];
    if (selected && run.status === "running") {
      list.push({ id: "take", label: "Take control of the browser", run: () => api.takeOver(selected, "user").catch(() => undefined) });
      list.push({ id: "stop", label: "Stop this run", run: () => api.stopRun(selected).then(refresh) });
    }
    return list;
  }, [selected, run.status, refresh, collapsed, setSelected]);

  return (
    <div className={collapsed ? "app sidebar-collapsed" : "app"}>
      <Sidebar runs={runs} selected={selected} collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} onSelect={open}
        onNew={() => setSelected(null)} onSettings={() => setSettingsOpen(true)} onSearch={() => setPaletteOpen(true)} />
      <main className="main">
        {selected
          ? <MissionView key={selected} runId={selected} task={runs.find((r) => r.id === selected)?.task ?? ""} run={run} frame={frame} send={send} onChanged={refresh} onOpen={open} />
          : <NewRun onStarted={open} />}
      </main>
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} runs={runs} commands={commands} onOpenRun={open} />
    </div>
  );
}

export default function App() {
  return <SettingsProvider><Workbench /></SettingsProvider>;
}
