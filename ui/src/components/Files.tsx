import { Download } from "lucide-react";
import type { ViewFile } from "../viewFiles";

export const size = (n: number) => (n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1000))} KB`);
const kind = (name: string) => (name.split(".").pop() || "file").slice(0, 4).toUpperCase();

function FileRow({ file, onOpen }: { file: ViewFile; onOpen: () => void }) {
  return (
    <li className="file">
      <button className="file-open" onClick={onOpen} title="Preview">
        <span className="file-kind">{kind(file.name)}</span>
        <span className="file-body">
          <span className="file-name" title={file.name}>{file.name}</span>
          <span className="hint">{file.size ? `${size(file.size)} · ` : ""}{file.label}</span>
        </span>
      </button>
      <a className="icon-btn" href={file.downloadUrl} download title="Download" aria-label={`Download ${file.name}`}><Download size={15} /></a>
    </li>
  );
}

/** Everything the run saved or produced, as a downloads list; clicking one previews it. */
export function Files({ files, onOpen }: { files: ViewFile[]; onOpen: (key: string) => void }) {
  if (!files.length) return null;
  return (
    <section className="files">
      <h4 className="section-h">Files <span className="count">{files.length}</span></h4>
      <ul>{files.map((file) => <FileRow key={file.key} file={file} onOpen={() => onOpen(file.key)} />)}</ul>
    </section>
  );
}
