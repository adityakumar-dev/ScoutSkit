import { useEffect, useState } from "react";
import { api, type Row } from "../api";

const SHOWN = 200;

export function ResultTable({ runId, items, hasRecipe, onExpand }: { runId: string; items: number; hasRecipe: boolean; onExpand?: () => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    setRows([]);
    if (items > 0) api.rows(runId).then(setRows).catch(() => setRows([]));
  }, [runId, items]);

  if (!items) return null;
  const columns = rows.length ? Object.keys(rows[0]) : [];
  return (
    <section className="card">
      <div className="result-head">
        <h2>Result: {items} items</h2>
        <span className="downloads">
          {onExpand && <button className="ghost small-btn" onClick={onExpand}>⤢ Full view</button>}
          <a href={api.fileUrl(runId, "result.csv")} download>CSV</a>
          <a href={api.fileUrl(runId, "result.json")} download>JSON</a>
          {hasRecipe && <a href={api.fileUrl(runId, "recipe.json")} download>Recipe</a>}
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0, SHOWN).map((row, index) => (
              <tr key={index}>{columns.map((column) => <td key={column}>{row[column]?.slice(0, 140)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > SHOWN && <p className="hint">Showing the first {SHOWN} of {rows.length}; download the CSV for everything.</p>}
    </section>
  );
}
