import type { RunSummary } from "../api";
import { Composer } from "./Composer";
import { StatusPill } from "./StatusPill";

/** Landing: a single prompt, and the missions so far as cards. */
export function Home({ runs, onOpen }: { runs: RunSummary[]; onOpen: (id: string) => void }) {
  return (
    <div className="home">
      <section className="hero">
        <div className="logo-mark" aria-hidden>◆</div>
        <h1>What should your agents <span className="grad">explore</span>?</h1>
        <p className="sub">They plan, open the browser, work across tabs, and bring back evidence you can replay.</p>
        <Composer onStarted={onOpen} />
      </section>
      {runs.length > 0 && (
        <section className="recent">
          <h2>Recent missions <kbd>Ctrl K</kbd></h2>
          <div className="cards">
            {runs.slice(0, 12).map((run) => (
              <button key={run.id} className={`mission-card ${run.status}`} onClick={() => onOpen(run.id)}>
                <span className="mission-task">{run.task || "Untitled mission"}</span>
                <span className="mission-meta">
                  <StatusPill status={run.status} />
                  <span>{run.items} items{run.files?.length ? ` · ${run.files.length} files` : ""}</span>
                  <span className="mono">{run.id.slice(9, 11)}:{run.id.slice(11, 13)}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
