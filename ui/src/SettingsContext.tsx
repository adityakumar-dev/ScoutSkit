import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { applySettings, DEFAULTS, loadSettings, saveSettings, type Settings } from "./settings";

interface Value {
  settings: Settings;
  update: (change: Partial<Settings> | ((current: Settings) => Settings)) => void;
  reset: () => void;
}

const Ctx = createContext<Value>({ settings: DEFAULTS, update: () => undefined, reset: () => undefined });

const dark = () => window.matchMedia("(prefers-color-scheme: dark)");

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [prefersDark, setPrefersDark] = useState(() => dark().matches);

  useEffect(() => {
    const query = dark();
    const listen = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    query.addEventListener("change", listen);
    return () => query.removeEventListener("change", listen);
  }, []);

  useEffect(() => {
    applySettings(document.documentElement, settings, prefersDark);
    saveSettings(settings);
  }, [settings, prefersDark]);

  const update = useCallback((change: Partial<Settings> | ((current: Settings) => Settings)) => {
    setSettings((current) => (typeof change === "function" ? change(current) : { ...current, ...change }));
  }, []);
  const reset = useCallback(() => setSettings(DEFAULTS), []);
  const value = useMemo(() => ({ settings, update, reset }), [settings, update, reset]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useSettings = () => useContext(Ctx);
