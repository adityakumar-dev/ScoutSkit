import { describe, expect, it } from "vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { fromKey, fromPaste, makeBatcher, toFraction } from "./remoteInput";

const natural = { width: 1280, height: 800 };

describe("toFraction", () => {
  it("maps a point in a same-shaped box to fractions", () => {
    expect(toFraction(400, 250, { left: 100, top: 50, width: 800, height: 500 }, natural)).toEqual({ x: 0.375, y: 0.4 });
  });

  it("ignores the bars when the box is wider than the picture", () => {
    const box = { left: 0, top: 0, width: 1000, height: 400 }; // picture is 640x400, centred: bars of 180 on each side
    expect(toFraction(180, 0, box, natural)).toEqual({ x: 0, y: 0 });
    expect(toFraction(500, 200, box, natural)).toEqual({ x: 0.5, y: 0.5 });
    expect(toFraction(100, 200, box, natural)).toBeNull();
  });

  it("is null before the picture has a size", () => {
    expect(toFraction(1, 1, { left: 0, top: 0, width: 100, height: 100 }, { width: 0, height: 0 })).toBeNull();
  });
});

describe("fromKey", () => {
  const press = (key: string, extra = {}) => fromKey({ key, ctrlKey: false, metaKey: false, altKey: false, ...extra });

  it("types printable characters, including a space", () => {
    expect(press("a")).toEqual({ kind: "type", text: "a" });
    expect(press(" ")).toEqual({ kind: "type", text: " " });
  });

  it("sends the allowed named keys and nothing else", () => {
    expect(press("Enter")).toEqual({ kind: "key", key: "Enter" });
    expect(press("F12")).toBeNull();
    expect(press("Shift")).toBeNull();
  });

  it("sends the editing shortcuts and leaves the rest to your own browser", () => {
    expect(press("a", { ctrlKey: true })).toEqual({ kind: "key", key: "a", mods: ["Control"] });
    expect(press("Z", { ctrlKey: true })).toEqual({ kind: "key", key: "z", mods: ["Control"] });
    expect(press("r", { ctrlKey: true })).toBeNull(); // reload of THIS page
    expect(press("w", { ctrlKey: true })).toBeNull();
    expect(press("a", { altKey: true })).toBeNull();
  });
});

describe("fromPaste", () => {
  it("sends pasted text, cut to what the server accepts, and nothing for nothing", () => {
    expect(fromPaste("hello")).toEqual({ kind: "type", text: "hello" });
    expect(fromPaste("x".repeat(5000))).toMatchObject({ kind: "type" });
    expect((fromPaste("x".repeat(5000)) as { text: string }).text).toHaveLength(2000);
    expect(fromPaste("")).toBeNull();
  });
});

describe("makeBatcher", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("turns a flood of scroll events into one message per interval, at the last pointer position", () => {
    const sent: number[][] = [];
    const batch = makeBatcher(50, (dy, x, y) => sent.push([dy, x, y]));
    for (let i = 0; i < 40; i++) batch.add(10, 0.1 * (i % 5), 0.5);
    expect(sent).toEqual([]);
    vi.advanceTimersByTime(50);
    expect(sent).toEqual([[400, 0.4, 0.5]]);
    batch.add(-30, 0.2, 0.2);
    vi.advanceTimersByTime(50);
    expect(sent[1]).toEqual([-30, 0.2, 0.2]);
  });

  it("caps one batch at what the server accepts, drops a batch that cancels out, and can be cancelled", () => {
    const sent: number[] = [];
    const batch = makeBatcher(50, (dy) => sent.push(dy));
    batch.add(99999, 0, 0);
    vi.advanceTimersByTime(50);
    batch.add(5, 0, 0);
    batch.add(-5, 0, 0);
    vi.advanceTimersByTime(50);
    batch.add(7, 0, 0);
    batch.cancel();
    vi.advanceTimersByTime(100);
    expect(sent).toEqual([5000]);
  });
});
