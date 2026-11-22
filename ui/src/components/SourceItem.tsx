import type { Source } from "../runState";

const LABEL: Record<string, string> = { web: "Web search", duckduckgo: "Web search", wikipedia: "Wikipedia", wikidata: "Wikidata", you: "you" };
const host = (url: string) => url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];

/** One search result: where it is, which search found it, and (for a pick) why the brain chose it. */
export function SourceItem({ source, rank }: { source: Source; rank?: number }) {
  return (
    <li className="source">
      {rank !== undefined && <span className="rank">{rank}</span>}
      <div className="source-body">
        <a href={source.url} target="_blank" rel="noreferrer" className="source-title">{source.title}</a>
        <div className="source-meta"><span className="mono">{host(source.url)}</span><span className={`tag ${source.source}`}>{LABEL[source.source] ?? source.source}</span></div>
        {source.why ? <p className="why">{source.why}</p> : source.snippet && <p className="snippet">{source.snippet}</p>}
      </div>
    </li>
  );
}
