// What a person can customise, kept in this browser. Everything read back from storage is validated: a bad or old value falls back to its default.

export type Theme = "system" | "light" | "dark";
export type Density = "compact" | "comfortable";
export type PanelSide = "right" | "bottom";
export type PanelTab = "Plan" | "Agents" | "Activity" | "Data";

export const ACCENTS = {
  orange: "#d9480f",
  blue: "#1c6dd0",
  green: "#2b8a3e",
  plum: "#862e9c",
  slate: "#495057",
} as const;
export type AccentName = keyof typeof ACCENTS;

export interface Settings {
  theme: Theme;
  accent: AccentName | string; // a preset name or a #rrggbb colour
  density: Density;
  textSize: number; // percent of the normal size
  panelSide: PanelSide;
  startTab: PanelTab;
  ticker: boolean; // the line with the latest action at the bottom
  motion: boolean; // animations
  runDefaults: { autonomous: boolean; web: boolean; provider: string };
}

export const DEFAULTS: Settings = {
  theme: "system",
  accent: "orange",
  density: "comfortable",
  textSize: 100,
  panelSide: "right",
  startTab: "Activity",
  ticker: true,
  motion: true,
  runDefaults: { autonomous: false, web: false, provider: "" },
};

export const TEXT_SIZES = { min: 85, max: 125, step: 5 };
export const HEX = /^#[0-9a-fA-F]{6}$/;
const KEY = "scoutskit.settings.v1";

const pick = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T => (allowed.includes(value as T) ? (value as T) : fallback);

/** Settings from whatever was stored: anything missing or invalid gets its default. */
export function parseSettings(raw: unknown): Settings {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const d = DEFAULTS;
  const run = (o.runDefaults && typeof o.runDefaults === "object" ? o.runDefaults : {}) as Record<string, unknown>;
  const accent = typeof o.accent === "string" && (o.accent in ACCENTS || HEX.test(o.accent)) ? o.accent : d.accent;
  const size = typeof o.textSize === "number" && Number.isFinite(o.textSize) ? o.textSize : d.textSize;
  return {
    theme: pick(o.theme, ["system", "light", "dark"], d.theme),
    accent,
    density: pick(o.density, ["compact", "comfortable"], d.density),
    textSize: Math.min(TEXT_SIZES.max, Math.max(TEXT_SIZES.min, Math.round(size))),
    panelSide: pick(o.panelSide, ["right", "bottom"], d.panelSide),
    startTab: pick(o.startTab, ["Plan", "Agents", "Activity", "Data"], d.startTab),
    ticker: typeof o.ticker === "boolean" ? o.ticker : d.ticker,
    motion: typeof o.motion === "boolean" ? o.motion : d.motion,
    runDefaults: {
      autonomous: typeof run.autonomous === "boolean" ? run.autonomous : d.runDefaults.autonomous,
      web: typeof run.web === "boolean" ? run.web : d.runDefaults.web,
      provider: typeof run.provider === "string" ? run.provider.slice(0, 60) : d.runDefaults.provider,
    },
  };
}

export const accentColor = (accent: string): string => (accent in ACCENTS ? ACCENTS[accent as AccentName] : HEX.test(accent) ? accent : ACCENTS.orange);

/** A readable text colour (black or white) on top of the accent. */
export function onAccent(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#111111" : "#ffffff";
}

/** Put the settings on the page: attributes and variables on <html>, which the stylesheet reads. */
export interface Root {
  dataset: Record<string, string | undefined>;
  style: { fontSize: string; setProperty(name: string, value: string): void };
}

export function applySettings(root: Root, s: Settings, prefersDark: boolean): void {
  const dark = s.theme === "dark" || (s.theme === "system" && prefersDark);
  const accent = accentColor(s.accent);
  root.dataset.theme = dark ? "dark" : "light";
  root.dataset.density = s.density;
  root.dataset.motion = s.motion ? "on" : "off";
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--on-accent", onAccent(accent));
  root.style.fontSize = `${s.textSize}%`;
}

export function loadSettings(storage: Pick<Storage, "getItem"> = localStorage): Settings {
  try {
    return parseSettings(JSON.parse(storage.getItem(KEY) ?? "null"));
  } catch {
    return DEFAULTS;
  }
}

export function saveSettings(s: Settings, storage: Pick<Storage, "setItem"> = localStorage): void {
  try {
    storage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* private window or storage full: the settings last for this visit only */
  }
}
