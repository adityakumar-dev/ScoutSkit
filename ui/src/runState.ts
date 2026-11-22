// The state of one run, built only from the events the server streams (so the same code shows a live run and a finished one).

import type { Control, RunEvent, RunStatus } from "./api";

export interface StepView {
  step: number;
  tool: string;
  detail: string;
  ok: boolean;
  outcome: string;
  screenshot: string;
  agent: string;
}

export interface Tab {
  index: number;
  title: string;
  url: string;
  active: boolean;
}

export interface Plan {
  goal: string;
  startUrl: string;
  item: string;
  fields: string[];
  minItems: number;
}

export interface Source {
  title: string;
  url: string;
  snippet: string;
  source: string; // which search found it: duckduckgo, wikipedia, wikidata, or "you"
  why?: string; // for the brain's picks: why it chose this one
}

export interface Brief {
  understanding: string;
  picks: Source[];
  sources: Source[];
  steps: string[];
  questions: string[];
  notes: string[]; // search sources that failed
  queries: string[];
  context: string;
  startUrl: string;
  agents: number; // sub-agents that will start, one per pick
}

/** Where the plan is: "" before one exists, "waiting" for the person, "revising" with their context, "approved". */
export type Approval = "" | "waiting" | "revising" | "approved";

/** A sub-agent met a check only a person can pass (a CAPTCHA) and is waiting for them. */
export interface HelpRequest {
  agent: string;
  host: string;
  url: string;
}

export interface TodoItem {
  text: string;
  status: "todo" | "doing" | "done" | "skipped";
}

/** One worker of the run. The main agent always exists; sub-agents appear when the server announces them. */
export interface AgentView {
  id: string;
  name: string;
  task: string;
  tab: string; // which tab it works in: "own", "copy of tab 0", or "" for the main agent
  status: "running" | "done" | "failed" | "stopped";
  url: string; // the source it started from
  verdict: string; // the brain's check of its result
  steps: number;
  last: string;
  report: string;
}

export const MAIN = "main";

export interface SavedFile {
  name: string;
  url: string;
  size: number;
  contentType: string;
  agent: string;
}

/** A sub-agent finished; the brain thinks it is complete and asks the person to accept it. */
export interface ResultCheck {
  agent: string;
  name: string;
  items: number;
  files: string[];
  why: string;
  url: string;
  doubt: boolean; // the brain doubts this result: you decide
  state: "waiting" | "approved" | "rejected";
}

export interface RunView {
  status: RunStatus;
  notices: string[];
  steps: StepView[];
  items: number;
  message: string;
  hasRecipe: boolean;
  control: Control;
  inputNotice: string; // why the last input was refused, until control changes
  plan: Plan | null;
  todo: TodoItem[];
  tabs: Tab[];
  agents: AgentView[];
  brief: Brief | null;
  approval: Approval;
  focus: string; // the sub-agent whose browser is shown
  help: HelpRequest | null;
  files: SavedFile[];
  resultCheck: ResultCheck | null;
  seconds: number; // run time so far, from the events' clocks
  provider: string;
}

const mainAgent: AgentView = { id: MAIN, name: "Main brain", task: "", tab: "", status: "running", steps: 0, last: "", report: "", url: "", verdict: "" };

export const emptyRun: RunView = { status: "running", notices: [], steps: [], items: 0, message: "", hasRecipe: false, control: "agent", inputNotice: "", plan: null, todo: [], tabs: [], agents: [mainAgent], brief: null, approval: "", focus: "", help: null, files: [], resultCheck: null, seconds: 0, provider: "" };

export type Phase = "plan" | "explore" | "extract" | "done";
export const PHASES: Phase[] = ["plan", "explore", "extract", "done"];

/** Where the run is, for the progress rail: planning until there is a plan, exploring until something is collected. */
export function phaseOf(run: RunView): Phase {
  if (run.status !== "running") return "done";
  if (run.approval === "waiting" || run.approval === "revising") return "plan";
  if (run.items > 0) return "extract";
  return run.plan || run.steps.length ? "explore" : "plan";
}

export const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

const text = (value: unknown): string => (typeof value === "string" ? value : "");

/** A short human description of what the step acted on. */
export function describe(event: RunEvent): string {
  const label = text(event.label);
  const args = (event.args ?? {}) as Record<string, unknown>;
  if (label) return label;
  const first = Object.values(args).find((value) => typeof value === "string" || typeof value === "number");
  return first === undefined ? "" : String(first).slice(0, 80);
}

const strings = (value: unknown): string[] => (Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : []);

const sources = (value: unknown): Source[] =>
  Array.isArray(value)
    ? value.map((v) => ({ title: text(v?.title), url: text(v?.url), snippet: text(v?.snippet), source: text(v?.source), why: text(v?.why) || undefined }))
    : [];

const updateAgent = (agents: AgentView[], id: string, change: (agent: AgentView) => AgentView): AgentView[] => agents.map((a) => (a.id === id ? change(a) : a));

export function applyEvent(run: RunView, event: RunEvent): RunView {
  const t = typeof event.t === "number" ? event.t : 0;
  const next = applyKnown(run, event);
  return t > next.seconds ? { ...next, seconds: t } : next;
}

function applyKnown(run: RunView, event: RunEvent): RunView {
  switch (event.type) {
    case "notice":
      return { ...run, notices: [...run.notices, text(event.text)] };
    case "plan":
      return {
        ...run,
        plan: { goal: text(event.goal), startUrl: text(event.start_url), item: text(event.item_name), fields: strings(event.fields), minItems: Number(event.min_items ?? 0) },
        agents: updateAgent(run.agents, MAIN, (a) => ({ ...a, task: `coordinates: ${text(event.goal)}` })),
      };
    case "brief":
      return {
        ...run,
        brief: {
          understanding: text(event.understanding), picks: sources(event.picks), sources: sources(event.sources), steps: strings(event.steps),
          questions: strings(event.questions), notes: strings(event.notes), queries: strings(event.queries), context: text(event.context), startUrl: text(event.start_url),
          agents: Number(event.agents ?? 1),
        },
      };
    case "approval": {
      const state = text(event.state);
      if (text(event.topic) === "result") {
        return run.resultCheck ? { ...run, resultCheck: { ...run.resultCheck, state: state as ResultCheck["state"] } } : run;
      }
      return { ...run, approval: state as Approval };
    }
    case "result_check":
      return {
        ...run,
        resultCheck: { agent: text(event.agent), name: text(event.name), items: Number(event.items ?? 0), files: strings(event.files), why: text(event.why), url: text(event.url), doubt: event.doubt === true, state: "waiting" },
      };
    case "verify":
      return { ...run, agents: updateAgent(run.agents, text(event.agent), (a) => ({ ...a, verdict: `${event.complete ? "✓" : "✗"} ${text(event.why)}` })) };
    case "focus":
      return { ...run, focus: text(event.agent) };
    case "file":
      return {
        ...run,
        files: [...run.files, { name: text(event.name), url: text(event.url), size: Number(event.size ?? 0), contentType: text(event.content_type), agent: text(event.agent) }],
      };
    case "todo":
      return { ...run, todo: Array.isArray(event.items) ? (event.items as TodoItem[]).map((i) => ({ text: text(i.text), status: i.status ?? "todo" })) : run.todo };
    case "tabs":
      return { ...run, tabs: Array.isArray(event.tabs) ? (event.tabs as Tab[]) : run.tabs };
    case "agent": {
      const id = text(event.agent);
      if (!id || id === MAIN) return run;
      const known = run.agents.some((a) => a.id === id);
      const fresh: AgentView = {
        id, name: text(event.name) || id, task: text(event.task), tab: text(event.tab), status: "running", steps: 0, last: "", report: "", url: text(event.url), verdict: "",
      };
      const agents = known ? run.agents : [...run.agents, fresh];
      return {
        ...run,
        agents: updateAgent(agents, id, (a) => ({
          ...a,
          name: text(event.name) || a.name,
          task: text(event.task) || a.task,
          tab: text(event.tab) || a.tab,
          status: (text(event.status) || a.status) as AgentView["status"],
          report: text(event.report) || a.report,
          url: text(event.url) || a.url,
        })),
      };
    }
    case "step": {
      const who = text(event.agent) || MAIN;
      const detail = describe(event);
      return {
        ...run,
        agents: updateAgent(run.agents, who, (a) => ({ ...a, steps: a.steps + 1, last: `${text(event.tool)} ${detail}`.trim() })),
        items: typeof event.collected === "number" ? event.collected : run.items,
        steps: [
          ...run.steps,
          {
            step: Number(event.step ?? run.steps.length + 1),
            tool: text(event.tool) || "(no tool call)",
            detail: describe(event),
            ok: event.ok !== false,
            outcome: text(event.error) || text(event.outcome),
            screenshot: text(event.screenshot),
            agent: who,
          },
        ],
      };
    }
    case "start":
      return { ...run, provider: Array.isArray(event.providers) ? text(event.providers[0]) : run.provider };
    case "provider_switch":
      return { ...run, provider: text(event.to) || run.provider };
    case "help_needed":
      return { ...run, help: { agent: text(event.agent), host: text(event.host), url: text(event.url) } };
    case "help_done":
      return { ...run, help: null };
    case "control":
      return { ...run, control: text(event.mode) as Control, inputNotice: "", help: text(event.mode) === "agent" ? null : run.help };
    case "input_refused":
      return { ...run, inputNotice: text(event.reason) };
    case "finished":
      return {
        ...run,
        control: "agent",
        help: null,
        status: text(event.status) as RunStatus,
        approval: run.approval === "approved" ? "approved" : "",
        resultCheck: run.resultCheck && run.resultCheck.state === "waiting" ? null : run.resultCheck,
        items: typeof event.items === "number" ? event.items : run.items,
        message: text(event.message),
        hasRecipe: event.recipe === true,
        agents: run.agents.map((a) => (a.status === "running" ? { ...a, status: a.id === MAIN && text(event.status) === "completed" ? "done" : a.id === MAIN ? "failed" : "stopped" } : a)),
      };
    default:
      return run;
  }
}
