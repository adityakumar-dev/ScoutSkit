import { useState } from "react";
import { Monitor, Moon, RotateCcw, Sun, X } from "lucide-react";
import { useSettings } from "../SettingsContext";
import { ACCENTS, HEX, TEXT_SIZES, accentColor, type AccentName, type PanelTab } from "../settings";
import { Segmented } from "./Segmented";

const TABS: PanelTab[] = ["Plan", "Agents", "Activity", "Data"];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="set-row">
      <div className="set-label"><span>{label}</span>{hint && <small className="muted">{hint}</small>}</div>
      <div className="set-control">{children}</div>
    </div>
  );
}

function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <button type="button" role="switch" aria-checked={on} aria-label={label} className={on ? "switch on" : "switch"} onClick={() => onChange(!on)}><i /></button>;
}

/** Everything that can be customised. Changes apply at once and are remembered in this browser. */
export function SettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { settings: s, update, reset } = useSettings();
  const [hex, setHex] = useState("");
  if (!open) return null;
  const custom = !(s.accent in ACCENTS);
  const applyHex = (value: string) => {
    setHex(value);
    const withHash = value.startsWith("#") ? value : `#${value}`;
    if (HEX.test(withHash)) update({ accent: withHash.toLowerCase() });
  };
  return (
    <div className="scrim" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-label="Settings" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head"><h2>Settings</h2><button className="icon-btn" onClick={onClose} aria-label="Close settings"><X size={16} /></button></header>
        <div className="drawer-body">
          <section>
            <h3>Appearance</h3>
            <Row label="Theme">
              <Segmented label="Theme" value={s.theme} onChange={(theme) => update({ theme })} options={[
                { value: "system", label: <><Monitor size={14} /> System</> }, { value: "light", label: <><Sun size={14} /> Light</> }, { value: "dark", label: <><Moon size={14} /> Dark</> },
              ]} />
            </Row>
            <Row label="Accent colour">
              <div className="swatches" role="radiogroup" aria-label="Accent colour">
                {(Object.keys(ACCENTS) as AccentName[]).map((name) => (
                  <button key={name} type="button" role="radio" aria-checked={s.accent === name} aria-label={name} title={name}
                    className={s.accent === name ? "swatch on" : "swatch"} style={{ background: ACCENTS[name] }} onClick={() => { setHex(""); update({ accent: name }); }} />
                ))}
                <input className="hex" value={custom && !hex ? s.accent : hex} onChange={(e) => applyHex(e.target.value.trim())} placeholder="#hex" maxLength={7} aria-label="Custom accent colour"
                  style={custom ? { borderColor: accentColor(s.accent) } : undefined} />
              </div>
            </Row>
            <Row label="Density" hint="Spacing in lists and panels">
              <Segmented label="Density" value={s.density} onChange={(density) => update({ density })} options={[{ value: "comfortable", label: "Comfortable" }, { value: "compact", label: "Compact" }]} />
            </Row>
            <Row label="Text size" hint={`${s.textSize}%`}>
              <input type="range" min={TEXT_SIZES.min} max={TEXT_SIZES.max} step={TEXT_SIZES.step} value={s.textSize} onChange={(e) => update({ textSize: Number(e.target.value) })} aria-label="Text size" />
            </Row>
            <Row label="Animations"><Switch on={s.motion} onChange={(motion) => update({ motion })} label="Animations" /></Row>
          </section>

          <section>
            <h3>Layout</h3>
            <Row label="Inspector position" hint="Plan, agents, activity, data">
              <Segmented label="Inspector position" value={s.panelSide} onChange={(panelSide) => update({ panelSide })} options={[{ value: "right", label: "Right" }, { value: "bottom", label: "Bottom" }]} />
            </Row>
            <Row label="Open on tab">
              <select value={s.startTab} onChange={(e) => update({ startTab: e.target.value as PanelTab })} aria-label="Default inspector tab">{TABS.map((t) => <option key={t}>{t}</option>)}</select>
            </Row>
            <Row label="Latest-action line" hint="At the bottom of a run"><Switch on={s.ticker} onChange={(ticker) => update({ ticker })} label="Latest action line" /></Row>
          </section>

          <section>
            <h3>New-run defaults</h3>
            <Row label="Run on its own" hint="Skip plan approval"><Switch on={s.runDefaults.autonomous} onChange={(autonomous) => update({ runDefaults: { ...s.runDefaults, autonomous } })} label="Run on its own" /></Row>
            <Row label="Any public website" hint="When you name a start site"><Switch on={s.runDefaults.web} onChange={(web) => update({ runDefaults: { ...s.runDefaults, web } })} label="Any public website" /></Row>
            <Row label="Model">
              <input value={s.runDefaults.provider} onChange={(e) => update({ runDefaults: { ...s.runDefaults, provider: e.target.value.slice(0, 60) } })} placeholder="scoutskit.toml default" aria-label="Default model" />
            </Row>
          </section>
        </div>
        <footer className="drawer-foot">
          <button className="btn ghost" onClick={() => { setHex(""); reset(); }}><RotateCcw size={14} /> Reset to defaults</button>
          <span className="muted small">Saved in this browser</span>
        </footer>
      </aside>
    </div>
  );
}
