import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, type RunEvent } from "./api";
import type { RemoteInput } from "./remoteInput";
import { applyEvent, emptyRun, type RunView } from "./runState";

const RECONNECT_MS = 1000;

type Action = { kind: "reset" } | { kind: "event"; event: RunEvent };

function reduce(run: RunView, action: Action): RunView {
  return action.kind === "reset" ? emptyRun : applyEvent(run, action.event);
}

/** Follows one run over its WebSocket: events build the run view, binary messages are the live picture. */
export function useRunStream(runId: string | null) {
  const [run, dispatch] = useReducer(reduce, emptyRun);
  const [frame, setFrame] = useState<string | null>(null);
  const finished = useRef(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    dispatch({ kind: "reset" });
    setFrame(null);
    finished.current = false;
    if (!runId) return;

    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let closed = false;
    let lastFrame: string | null = null;

    const connect = () => {
      socket = new WebSocket(api.streamUrl(runId));
      socketRef.current = socket;
      socket.binaryType = "blob";
      socket.onopen = () => dispatch({ kind: "reset" }); // the server replays the whole history on every connection
      socket.onmessage = (message) => {
        if (message.data instanceof Blob) {
          const url = URL.createObjectURL(message.data);
          if (lastFrame) URL.revokeObjectURL(lastFrame);
          lastFrame = url;
          setFrame(url);
          return;
        }
        const event = JSON.parse(message.data) as RunEvent;
        if (event.type === "finished") finished.current = true;
        dispatch({ kind: "event", event });
      };
      socket.onclose = () => {
        if (!closed && !finished.current) retry = window.setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();

    return () => {
      closed = true;
      window.clearTimeout(retry);
      socket?.close();
      if (lastFrame) URL.revokeObjectURL(lastFrame);
    };
  }, [runId]);

  const send = useCallback((input: RemoteInput) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify(input));
  }, []);

  return { run, frame, send };
}
