import { useEffect, useState } from "react";
import { kindOf, parseCsv, prettyJson } from "../fileKinds";
import type { ViewFile } from "../viewFiles";
import { size } from "./Files";
import { PdfView } from "./PdfView";

const MAX_TEXT_BYTES = 2_000_000; // bigger files are cut here; the download is complete
const MAX_ROWS = 1000;

type Loaded = { state: "loading" } | { state: "error"; message: string } | { state: "text"; text: string; cut: boolean };

/** Text files are fetched here and drawn by React (escaped), never inserted as markup. */
function useText(url: string, wanted: boolean): Loaded {
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  useEffect(() => {
    if (!wanted) return;
    let cancelled = false;
    setLoaded({ state: "loading" });
    fetch(url)
      .then(async (response) => {
        if (!response.ok) throw new Error(`the server answered ${response.status}`);
        const text = await response.text();
        if (!cancelled) setLoaded({ state: "text", text: text.slice(0, MAX_TEXT_BYTES), cut: text.length > MAX_TEXT_BYTES });
      })
      .catch((failure) => !cancelled && setLoaded({ state: "error", message: failure instanceof Error ? failure.message : String(failure) }));
    return () => { cancelled = true; };
  }, [url, wanted]);
  return loaded;
}

function Table({ text, delimiter }: { text: string; delimiter: string }) {
  const [filter, setFilter] = useState("");
  const [head, ...body] = parseCsv(text, delimiter);
  if (!head) return <p className="hint">This file is empty.</p>;
  const needle = filter.trim().toLowerCase();
  const matching = needle ? body.filter((row) => row.some((cell) => cell.toLowerCase().includes(needle))) : body;
  return (
    <div className="viewer-table">
      <div className="viewer-tools">
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={`Filter ${body.length} rows…`} aria-label="Filter rows" />
        <span className="hint">{matching.length === body.length ? `${body.length} rows` : `${matching.length} of ${body.length} rows`} · {head.length} columns</span>
      </div>
      <div className="table-wrap tall">
        <table>
          <thead><tr><th className="row-no">#</th>{head.map((cell, i) => <th key={i}>{cell}</th>)}</tr></thead>
          <tbody>
            {matching.slice(0, MAX_ROWS).map((row, r) => (
              <tr key={r}><td className="row-no">{r + 1}</td>{head.map((_, c) => <td key={c} title={row[c]}>{row[c]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {matching.length > MAX_ROWS && <p className="hint">Showing the first {MAX_ROWS} rows; download the file for everything.</p>}
    </div>
  );
}

function Body({ file }: { file: ViewFile }) {
  const kind = kindOf(file.name);
  const text = useText(file.url, kind === "csv" || kind === "json" || kind === "text");
  if (kind === "pdf") return <PdfView url={file.url} />;
  if (kind === "image") return <div className="viewer-image"><img src={file.url} alt={file.name} /></div>;
  if (kind === "other") {
    return (
      <div className="viewer-none">
        <p>No preview for this kind of file.</p>
        <a className="primary" href={file.downloadUrl} download>⤓ Download {file.name}</a>
      </div>
    );
  }
  if (text.state === "loading") return <p className="hint viewer-pad">Loading…</p>;
  if (text.state === "error") return <p className="error viewer-pad">Could not load the file: {text.message}</p>;
  return (
    <>
      {kind === "csv" ? <Table text={text.text} delimiter={file.name.toLowerCase().endsWith(".tsv") ? "\t" : ","} />
        : <pre className="viewer-text">{kind === "json" ? prettyJson(text.text) : text.text}</pre>}
      {text.cut && <p className="hint viewer-pad">Showing the first {MAX_TEXT_BYTES / 1_000_000} MB; download the file for everything.</p>}
    </>
  );
}

/** A full-screen preview of one file: PDFs, images, tables (CSV/TSV, searchable), JSON and plain text. ← → move between files, Esc closes. */
export function FileViewer({ files, current, onChange, onClose }: { files: ViewFile[]; current: string; onChange: (key: string) => void; onClose: () => void }) {
  const index = files.findIndex((f) => f.key === current);
  const file = files[index];
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      const inField = (event.target as HTMLElement)?.tagName === "INPUT";
      if (!inField && event.key === "ArrowRight" && index < files.length - 1) onChange(files[index + 1].key);
      if (!inField && event.key === "ArrowLeft" && index > 0) onChange(files[index - 1].key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [files, index, onChange, onClose]);
  if (!file) return null;
  return (
    <div className="viewer-backdrop" onClick={onClose}>
      <div className="viewer" role="dialog" aria-label={`Viewing ${file.name}`} onClick={(e) => e.stopPropagation()}>
        <header className="viewer-head">
          <div className="viewer-title">
            <strong title={file.name}>{file.name}</strong>
            <span className="hint">{file.label}{file.size ? ` · ${size(file.size)}` : ""}</span>
          </div>
          {files.length > 1 && (
            <div className="viewer-nav">
              <button className="ghost" disabled={index === 0} onClick={() => onChange(files[index - 1].key)} aria-label="Previous file">←</button>
              <span className="mono">{index + 1}/{files.length}</span>
              <button className="ghost" disabled={index === files.length - 1} onClick={() => onChange(files[index + 1].key)} aria-label="Next file">→</button>
            </div>
          )}
          <a className="ghost" href={file.url} target="_blank" rel="noreferrer" title="Open in a new tab">↗</a>
          <a className="primary" href={file.downloadUrl} download>⤓ Download</a>
          <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="viewer-body"><Body key={file.key} file={file} /></div>
      </div>
    </div>
  );
}
