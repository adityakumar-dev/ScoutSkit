import { useEffect, useMemo, useRef, useState } from "react";
import { fromKey, fromPaste, makeBatcher, toFraction, type RemoteInput } from "../remoteInput";
import type { RunView } from "../runState";

const SCROLL_EVERY_MS = 50; // scroll events arrive dozens of times a second: send them in batches
const HOVER_EVERY_MS = 100;
const RIPPLE_MS = 600;

interface Props {
  runId: string;
  run: RunView;
  frame: string | null;
  screenshotUrl: (shot: string) => string;
  send: (input: RemoteInput) => void;
}

interface Ripple {
  id: number;
  left: number;
  top: number;
  right: boolean;
}

/** The browser as the agent sees it: the live stream while the run goes, the last step's screenshot afterwards. A person driving can click, scroll, type, hover and paste in it. */
export function LiveView({ runId, run, frame, screenshotUrl, send }: Props) {
  const image = useRef<HTMLImageElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const sendRef = useRef(send);
  sendRef.current = send;
  const lastHover = useRef(0);
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const driving = run.control === "user" && run.status === "running";
  const last = [...run.steps].reverse().find((step) => step.screenshot);
  const src = run.status === "running" ? frame : last ? screenshotUrl(last.screenshot) : frame;

  const where = (clientX: number, clientY: number) => {
    const el = image.current;
    return el ? toFraction(clientX, clientY, el.getBoundingClientRect(), { width: el.naturalWidth, height: el.naturalHeight }) : null;
  };

  const ripple = (event: { clientX: number; clientY: number }, right: boolean) => {
    const area = box.current?.getBoundingClientRect();
    if (!area) return;
    const id = Date.now() + Math.random();
    setRipples((current) => [...current, { id, left: event.clientX - area.left, top: event.clientY - area.top, right }]);
    window.setTimeout(() => setRipples((current) => current.filter((r) => r.id !== id)), RIPPLE_MS);
  };

  // Scrolling must not also scroll this page, which needs a non-passive listener (React's onWheel is passive). Batched, so a trackpad cannot flood the browser.
  const batcher = useMemo(() => makeBatcher(SCROLL_EVERY_MS, (dy, x, y) => sendRef.current({ kind: "scroll", x, y, dy })), []);
  useEffect(() => {
    const el = box.current;
    if (!driving || !el) return;
    const onWheel = (event: WheelEvent) => {
      const at = where(event.clientX, event.clientY);
      if (!at) return;
      event.preventDefault();
      batcher.add(event.deltaY, at.x, at.y);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", onWheel);
      batcher.cancel();
    };
  }, [driving, batcher]);

  const onClick = (event: React.MouseEvent) => {
    const at = driving ? where(event.clientX, event.clientY) : null;
    if (!at) return;
    ripple(event, false);
    box.current?.focus(); // so the keys go to the page
    send({ kind: "click", ...at, clicks: Math.min(3, Math.max(1, event.detail || 1)) });
  };

  return (
    <div
      ref={box}
      className={driving ? "live driving" : "live"}
      tabIndex={driving ? 0 : -1}
      onKeyDown={(event) => {
        if (!driving) return;
        const input = fromKey(event);
        if (input) {
          event.preventDefault();
          send(input);
        }
      }}
      onPaste={(event) => {
        const input = driving ? fromPaste(event.clipboardData.getData("text")) : null;
        if (input) {
          event.preventDefault();
          send(input);
        }
      }}
      onMouseMove={(event) => {
        const now = Date.now();
        if (!driving || now - lastHover.current < HOVER_EVERY_MS) return;
        const at = where(event.clientX, event.clientY);
        if (at) {
          lastHover.current = now;
          send({ kind: "move", ...at }); // menus that open on hover need the pointer to be there
        }
      }}
      onContextMenu={(event) => {
        if (!driving) return;
        event.preventDefault();
        const at = where(event.clientX, event.clientY);
        if (at) {
          ripple(event, true);
          send({ kind: "click", ...at, button: "right" });
        }
      }}
    >
      {src ? (
        <img ref={image} key={runId} src={src} alt="The browser the agent is working in" draggable={false} onClick={onClick} />
      ) : (
        <div className="live-empty">{run.status === "running" ? "Waiting for the browser…" : "No picture for this run."}</div>
      )}
      {ripples.map((r) => <span key={r.id} className={r.right ? "ripple right" : "ripple"} style={{ left: r.left, top: r.top }} />)}
      {driving && <span className="drive-hint">You're driving · click, scroll, type, paste</span>}
    </div>
  );
}
