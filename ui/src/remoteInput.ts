// Turning what a person does in the live view into the inputs the server accepts (see server/remote_input.py).

export type RemoteInput =
  | { kind: "click"; x: number; y: number; button?: "left" | "right" | "middle"; clicks?: number }
  | { kind: "move"; x: number; y: number }
  | { kind: "scroll"; x: number; y: number; dy: number }
  | { kind: "type"; text: string }
  | { kind: "key"; key: string; mods?: ("Shift" | "Control" | "Alt")[] }
  | { kind: "navigate"; url: string }
  | { kind: "new_tab"; url: string }
  | { kind: "switch_tab" | "close_tab"; index: number }
  | { kind: "back" | "reload" | "duplicate_tab" };

const KEYS = new Set(["Enter", "Tab", "Backspace", "Delete", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);

interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Where on the page a pointer position is, as fractions (0..1) of the picture.
 * The picture is drawn with object-fit: contain, so bars around it do not count; null when the pointer is on a bar.
 */
export function toFraction(clientX: number, clientY: number, box: Box, natural: { width: number; height: number }) {
  if (!natural.width || !natural.height || !box.width || !box.height) return null;
  const scale = Math.min(box.width / natural.width, box.height / natural.height);
  const shownWidth = natural.width * scale;
  const shownHeight = natural.height * scale;
  const x = (clientX - box.left - (box.width - shownWidth) / 2) / shownWidth;
  const y = (clientY - box.top - (box.height - shownHeight) / 2) / shownHeight;
  return x < 0 || x > 1 || y < 0 || y > 1 ? null : { x, y };
}

const SHORTCUTS = new Set(["a", "z", "y"]); // select all, undo, redo (copy and cut cannot reach your clipboard; paste comes from the paste event)
export const MAX_PASTE = 2000;

/** A key press as an input: text for a printable character, a named key from the server's list, an editing shortcut; else null. */
export function fromKey(event: { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean }): RemoteInput | null {
  if (event.metaKey || event.altKey) return null;
  if (event.ctrlKey) return SHORTCUTS.has(event.key.toLowerCase()) && event.key.length === 1 ? { kind: "key", key: event.key.toLowerCase(), mods: ["Control"] } : null;
  if (event.key.length === 1) return { kind: "type", text: event.key };
  return KEYS.has(event.key) ? { kind: "key", key: event.key } : null;
}

/** Text pasted into the picture as an input, cut to what the server accepts; null when there is nothing to send. */
export function fromPaste(text: string): RemoteInput | null {
  return text ? { kind: "type", text: text.slice(0, MAX_PASTE) } : null;
}

/** Scroll events arrive dozens of times a second: this adds them up, and says when a batch is due (at most every `everyMs`). */
export function makeBatcher(everyMs: number, flush: (dy: number, x: number, y: number) => void) {
  let dy = 0;
  let at = { x: 0, y: 0 };
  let timer: ReturnType<typeof setTimeout> | null = null;
  return {
    add(delta: number, x: number, y: number) {
      dy += delta;
      at = { x, y };
      if (timer === null) {
        timer = setTimeout(() => {
          const total = dy;
          dy = 0;
          timer = null;
          if (total !== 0) flush(Math.max(-5000, Math.min(5000, total)), at.x, at.y);
        }, everyMs);
      }
    },
    cancel() {
      if (timer !== null) clearTimeout(timer);
      timer = null;
      dy = 0;
    },
  };
}
