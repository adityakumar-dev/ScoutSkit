import { useEffect, useRef, useState } from "react";
import type { SavedFile } from "../runState";
import { size } from "./Files";

const SHOW_MS = 9000;

/** Like a browser's download pop-up: appears when a file is saved during the run, offers to open it or see all files. */
export function DownloadBubble({ files, live, onOpen, onShowAll }: { files: SavedFile[]; live: boolean; onOpen: (name: string) => void; onShowAll: () => void }) {
  const seen = useRef(files.length);
  const [shown, setShown] = useState<SavedFile[]>([]);

  useEffect(() => {
    if (files.length > seen.current && live) {
      setShown(files.slice(seen.current));
      const timer = window.setTimeout(() => setShown([]), SHOW_MS);
      seen.current = files.length;
      return () => window.clearTimeout(timer);
    }
    seen.current = files.length;
  }, [files, live]);

  if (!shown.length) return null;
  const last = shown[shown.length - 1];
  return (
    <div className="bubble" role="status">
      <div className="bubble-head"><span className="bubble-icon">⤓</span><strong>{shown.length > 1 ? `${shown.length} files saved` : "File saved"}</strong><button className="bubble-x" onClick={() => setShown([])} aria-label="Close">×</button></div>
      <div className="bubble-file"><span className="file-name">{last.name}</span><span className="hint">{size(last.size)} · done</span></div>
      <div className="bubble-actions">
        <button className="ghost" onClick={() => { onOpen(last.name); setShown([]); }}>Open</button>
        <button className="ghost" onClick={() => { onShowAll(); setShown([]); }}>Show all files</button>
      </div>
    </div>
  );
}
