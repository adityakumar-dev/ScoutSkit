import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

interface Options {
  key: string; // where the size is remembered
  initial: number;
  min: number;
  max: number;
  axis: "x" | "y";
  reverse?: boolean; // dragging toward the start makes it bigger (a pane on the right or the bottom)
}

const read = (key: string, fallback: number) => {
  try {
    const value = Number(localStorage.getItem(`scoutskit.size.${key}`));
    return Number.isFinite(value) && value > 0 ? value : fallback;
  } catch {
    return fallback;
  }
};

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

/** A size the person can drag: returns it, the props for the drag handle, and a reset. Remembered per key. */
export function useResizable({ key, initial, min, max, axis, reverse }: Options) {
  const [size, setSize] = useState(() => clamp(read(key, initial), min, max));
  const drag = useRef<{ from: number; start: number } | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(`scoutskit.size.${key}`, String(Math.round(size)));
    } catch {
      /* not remembered */
    }
  }, [key, size]);

  const move = useCallback(
    (event: PointerEvent) => {
      if (!drag.current) return;
      const delta = (axis === "x" ? event.clientX : event.clientY) - drag.current.from;
      setSize(clamp(drag.current.start + (reverse ? -delta : delta), min, max));
    },
    [axis, reverse, min, max],
  );
  const stop = useCallback(() => {
    drag.current = null;
    document.body.classList.remove("resizing");
  }, []);

  useEffect(() => {
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
  }, [move, stop]);

  const handle = {
    onPointerDown: (event: ReactPointerEvent) => {
      event.preventDefault();
      drag.current = { from: axis === "x" ? event.clientX : event.clientY, start: size };
      document.body.classList.add("resizing");
    },
    onDoubleClick: () => setSize(clamp(initial, min, max)),
    onKeyDown: (event: React.KeyboardEvent) => {
      const step = event.shiftKey ? 40 : 10;
      const grow = axis === "x" ? "ArrowLeft" : "ArrowUp";
      const shrink = axis === "x" ? "ArrowRight" : "ArrowDown";
      if (event.key === grow || event.key === shrink) {
        event.preventDefault();
        setSize((s) => clamp(s + ((event.key === grow) === Boolean(reverse) ? step : -step), min, max));
      }
    },
    role: "separator" as const,
    tabIndex: 0,
    "aria-orientation": axis === "x" ? ("vertical" as const) : ("horizontal" as const),
    "aria-label": "Drag to resize, double-click to reset",
  };
  return { size, handle };
}
