// How the viewer shows a file, decided by its name; must stay in step with INLINE_TYPES in src/scoutskit/server/app.py.

export type FileKind = "pdf" | "image" | "csv" | "json" | "text" | "other";

const BY_EXTENSION: Record<string, FileKind> = {
  pdf: "pdf", png: "image", jpg: "image", jpeg: "image", gif: "image", webp: "image",
  csv: "csv", tsv: "csv", json: "json", txt: "text", md: "text", log: "text",
};

export const kindOf = (name: string): FileKind => BY_EXTENSION[name.split(".").pop()?.toLowerCase() ?? ""] ?? "other";

/** A CSV/TSV as rows of cells: quoted cells, doubled quotes and line breaks inside quotes are handled. */
export function parseCsv(text: string, delimiter = ","): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === delimiter) { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      rows.push(row); row = [];
    } else cell += c;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.length > 1 || r[0] !== "");
}

/** JSON made readable; text that is not valid JSON (a half-written file) is shown as it is. */
export function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}
