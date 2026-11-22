import { describe, expect, it } from "vitest";
import { accentColor, applySettings, DEFAULTS, loadSettings, onAccent, parseSettings, saveSettings } from "./settings";

describe("settings", () => {
  it("falls back to the defaults for anything missing, old or invalid", () => {
    expect(parseSettings(null)).toEqual(DEFAULTS);
    expect(parseSettings("nonsense")).toEqual(DEFAULTS);
    const odd = parseSettings({ theme: "neon", density: 3, panelSide: "left", startTab: "Nope", accent: "javascript:alert(1)", textSize: "big", ticker: "yes", runDefaults: { provider: 5 } });
    expect(odd).toEqual(DEFAULTS);
  });

  it("keeps valid choices, clamps the text size and accepts a preset or a hex colour", () => {
    const s = parseSettings({ theme: "dark", accent: "#12ab9f", textSize: 400, density: "compact", panelSide: "bottom", startTab: "Data", ticker: false, runDefaults: { autonomous: true, web: true, provider: "nvidia_super" } });
    expect(s).toMatchObject({ theme: "dark", accent: "#12ab9f", textSize: 125, density: "compact", panelSide: "bottom", startTab: "Data", ticker: false });
    expect(s.runDefaults).toEqual({ autonomous: true, web: true, provider: "nvidia_super" });
    expect(parseSettings({ accent: "green" }).accent).toBe("green");
    expect(parseSettings({ textSize: 20 }).textSize).toBe(85);
  });

  it("turns an accent into a colour, and picks readable text for it", () => {
    expect(accentColor("blue")).toBe("#1c6dd0");
    expect(accentColor("#abcdef")).toBe("#abcdef");
    expect(accentColor("bogus")).toBe("#d9480f");
    expect(onAccent("#ffffff")).toBe("#111111");
    expect(onAccent("#1c1c1c")).toBe("#ffffff");
  });

  it("round-trips through storage and survives broken storage", () => {
    const store: Record<string, string> = {};
    const fake = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => void (store[k] = v) };
    saveSettings({ ...DEFAULTS, theme: "light", textSize: 110 }, fake);
    expect(loadSettings(fake)).toMatchObject({ theme: "light", textSize: 110 });
    expect(loadSettings({ getItem: () => "{not json" })).toEqual(DEFAULTS);
    expect(() => saveSettings(DEFAULTS, { setItem: () => { throw new Error("full"); } })).not.toThrow();
  });

  it("applies the theme, density, accent and size to the page; system follows the OS", () => {
    const vars: Record<string, string> = {};
    const root = { dataset: {} as Record<string, string | undefined>, style: { fontSize: "", setProperty: (k: string, v: string) => void (vars[k] = v) } };
    applySettings(root, { ...DEFAULTS, theme: "system", density: "compact", textSize: 110, accent: "green" }, true);
    expect(root.dataset).toMatchObject({ theme: "dark", density: "compact", motion: "on" });
    expect(root.style.fontSize).toBe("110%");
    expect(vars["--accent"]).toBe("#2b8a3e");
    applySettings(root, { ...DEFAULTS, theme: "light", motion: false }, true);
    expect(root.dataset).toMatchObject({ theme: "light", motion: "off" });
  });
});
