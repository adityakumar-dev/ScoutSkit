import { api } from "../api";
import { MAIN, type AgentView, type RunView } from "../runState";

const SIZE = 300;
const CENTER = SIZE / 2;
const ORBIT = 105;
const host = (url: string) => url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];

function position(index: number, count: number) {
  const angle = -Math.PI / 2 + (index / Math.max(count, 1)) * Math.PI * 2;
  return { x: CENTER + ORBIT * Math.cos(angle), y: CENTER + ORBIT * Math.sin(angle) };
}

function Card({ agent, watching, canWatch, onWatch }: { agent: AgentView; watching: boolean; canWatch: boolean; onWatch: () => void }) {
  return (
    <li className={`agent-card ${agent.status}${watching ? " watching" : ""}`}>
      <div className="agent-head">
        <strong>{agent.name}</strong>
        <span className="agent-state">{watching ? "◉ watching" : agent.status}</span>
      </div>
      {agent.url ? <p className="mono small">{host(agent.url)}</p> : agent.task && <p>{agent.task}</p>}
      {agent.id !== MAIN && <p className="hint">{agent.steps} steps{agent.last ? ` · ${agent.last.slice(0, 70)}` : ""}</p>}
      {agent.report && <p className="agent-report">{agent.report}</p>}
      {agent.verdict && <p className={agent.verdict.startsWith("✓") ? "verdict ok" : "verdict no"}>Brain: {agent.verdict}</p>}
      {canWatch && !watching && <button className="ghost small-btn" onClick={onWatch}>Watch this browser</button>}
    </li>
  );
}

/** The main brain in the middle, its sub-agents around it; a link pulses while a sub-agent works. Click a sub-agent to watch its browser. */
export function AgentGraph({ runId, run }: { runId: string; run: RunView }) {
  const [main, ...subs] = run.agents;
  const live = run.status === "running" && run.control === "agent";
  const watch = (id: string) => api.focus(runId, id).catch(() => undefined);
  return (
    <div className="agents-view">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="graph" role="img" aria-label={`main brain and ${subs.length} sub-agents`}>
        <circle cx={CENTER} cy={CENTER} r={ORBIT} className="orbit" />
        {subs.map((agent, i) => {
          const at = position(i, subs.length);
          return (
            <g key={agent.id} className={live && agent.status === "running" ? "clickable" : ""} onClick={() => live && agent.status === "running" && watch(agent.id)}>
              <line x1={CENTER} y1={CENTER} x2={at.x} y2={at.y} className={`link ${agent.status}`} />
              <circle cx={at.x} cy={at.y} r={run.focus === agent.id ? 22 : 18} className={`node sub ${agent.status}${run.focus === agent.id ? " focus" : ""}`} />
              <text x={at.x} y={at.y + 4} className="node-num">{agent.id.slice(1)}</text>
              <text x={at.x} y={at.y + 38} className="node-label">{host(agent.url).slice(0, 18) || agent.name}</text>
            </g>
          );
        })}
        <circle cx={CENTER} cy={CENTER} r={34} className={`node core ${main.status}`} />
        <text x={CENTER} y={CENTER + 5} className="core-label">brain</text>
      </svg>
      {!subs.length && <p className="hint center">Sub-agents appear once the plan is approved: one per picked source, working in parallel.</p>}
      <ul className="agent-list">
        {run.agents.map((agent) => (
          <Card key={agent.id} agent={agent} watching={run.focus === agent.id && subs.length > 1} canWatch={live && agent.id !== MAIN && agent.status === "running" && subs.length > 1} onWatch={() => watch(agent.id)} />
        ))}
      </ul>
    </div>
  );
}
