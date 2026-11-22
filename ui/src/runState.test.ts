import { describe as suite, expect, it } from "vitest";
import { applyEvent, clock, describe, emptyRun, phaseOf } from "./runState";

suite("run state", () => {
  it("collects notices and steps in order and counts the items so far", () => {
    let run = applyEvent(emptyRun, { type: "notice", text: "planning" });
    run = applyEvent(run, { type: "step", step: 1, tool: "click", label: 'button "Load more"', ok: true, outcome: "clicked", collected: 0 });
    run = applyEvent(run, { type: "step", step: 2, tool: "extract_rows", args: { rows: [] }, ok: true, outcome: "+40 new", collected: 40 });
    expect(run.notices).toEqual(["planning"]);
    expect(run.steps.map((s) => [s.step, s.tool, s.detail])).toEqual([[1, "click", 'button "Load more"'], [2, "extract_rows", ""]]);
    expect(run.items).toBe(40);
    expect(run.status).toBe("running");
  });

  it("shows the error, not the outcome, of a failed step", () => {
    const run = applyEvent(emptyRun, { type: "step", step: 1, tool: "click", ok: false, error: "no such element", outcome: "" });
    expect(run.steps[0]).toMatchObject({ ok: false, outcome: "no such element" });
  });

  it("a step without a tool call is labelled, not blank", () => {
    expect(applyEvent(emptyRun, { type: "step", step: 3, tool: "", ok: false }).steps[0].tool).toBe("(no tool call)");
  });

  it("finishing sets the status, the final count and whether a recipe exists", () => {
    const run = applyEvent(emptyRun, { type: "finished", status: "completed", items: 265, message: "", recipe: true });
    expect(run).toMatchObject({ status: "completed", items: 265, hasRecipe: true });
  });

  it("ignores events it does not know", () => {
    expect(applyEvent(emptyRun, { type: "screenshot_failed", name: "step01" })).toBe(emptyRun);
  });

  it("describes a step by its target, else by its first simple argument", () => {
    expect(describe({ type: "step", args: { url: "https://x.test/a" } })).toBe("https://x.test/a");
    expect(describe({ type: "step", args: { rows: [1] } })).toBe("");
  });
});

suite("control", () => {
  it("follows who is driving and clears a refusal notice when that changes", () => {
    let run = applyEvent(emptyRun, { type: "control", mode: "requested" });
    expect(run.control).toBe("requested");
    run = applyEvent(applyEvent(run, { type: "control", mode: "user" }), { type: "input_refused", reason: "that input is not allowed" });
    expect(run).toMatchObject({ control: "user", inputNotice: "that input is not allowed" });
    expect(applyEvent(run, { type: "control", mode: "agent" })).toMatchObject({ control: "agent", inputNotice: "" });
  });

  it("a finished run is never left in someone's hands", () => {
    const run = applyEvent(applyEvent(emptyRun, { type: "control", mode: "user" }), { type: "finished", status: "completed", items: 1 });
    expect(run.control).toBe("agent");
  });
});

suite("plan, tabs and agents", () => {
  it("keeps the plan and the tabs the server announces", () => {
    let run = applyEvent(emptyRun, { type: "plan", goal: "Collect PS", start_url: "https://x.test", item_name: "problem statement", fields: ["id"], min_items: 10 });
    run = applyEvent(run, { type: "tabs", tabs: [{ index: 0, title: "X", url: "https://x.test", active: true }] });
    expect(run.plan).toMatchObject({ goal: "Collect PS", startUrl: "https://x.test", fields: ["id"], minItems: 10 });
    expect(run.tabs).toHaveLength(1);
    expect(run.agents[0]).toMatchObject({ id: "main", task: "coordinates: Collect PS" });
  });

  it("counts a step for the agent that took it, and lists sub-agents with their reports", () => {
    let run = applyEvent(emptyRun, { type: "agent", agent: "a1", name: "Scout 1", task: "check site B", tab: "own tab" });
    run = applyEvent(run, { type: "step", step: 1, tool: "click", agent: "a1", label: "link B", ok: true });
    run = applyEvent(run, { type: "step", step: 2, tool: "click", ok: true });
    run = applyEvent(run, { type: "agent", agent: "a1", status: "done", report: "found 3" });
    const [main, scout] = run.agents;
    expect([main.steps, scout.steps, scout.status, scout.report, scout.tab]).toEqual([1, 1, "done", "found 3", "own tab"]);
  });

  it("when the run ends, workers still running end with it", () => {
    const run = applyEvent(applyEvent(emptyRun, { type: "agent", agent: "a1" }), { type: "finished", status: "failed", items: 0 });
    expect(run.agents.map((a) => a.status)).toEqual(["failed", "stopped"]);
  });
});

suite("progress", () => {
  it("moves from planning to exploring to extracting to done, and keeps the run time", () => {
    let run = emptyRun;
    expect(phaseOf(run)).toBe("plan");
    run = applyEvent(run, { type: "plan", goal: "g", t: 3 });
    expect([phaseOf(run), run.seconds]).toEqual(["explore", 3]);
    run = applyEvent(run, { type: "step", step: 1, tool: "extract_rows", collected: 5, t: 75.5 });
    expect([phaseOf(run), clock(run.seconds)]).toEqual(["extract", "1:15"]);
    expect(phaseOf(applyEvent(run, { type: "finished", status: "completed", items: 5 }))).toBe("done");
  });

  it("names the provider in use, following a switch", () => {
    const run = applyEvent(applyEvent(emptyRun, { type: "start", providers: ["google", "nvidia_super"] }), { type: "provider_switch", to: "nvidia_super" });
    expect(run.provider).toBe("nvidia_super");
  });
});

suite("brief and approval", () => {
  it("keeps the brief, waits for the person, and stays in the plan phase until approved", () => {
    let run = applyEvent(emptyRun, {
      type: "brief", understanding: "wants the syllabus", start_url: "https://uni.example/s", steps: ["open", "find"], questions: [], notes: ["ddg gave nothing"],
      picks: [{ title: "Syllabus", url: "https://uni.example/s", snippet: "", source: "duckduckgo", why: "official" }], sources: [], queries: ["q"], context: "",
    });
    run = applyEvent(run, { type: "approval", state: "waiting" });
    expect(run.brief).toMatchObject({ understanding: "wants the syllabus", startUrl: "https://uni.example/s", notes: ["ddg gave nothing"] });
    expect(run.brief?.picks[0].why).toBe("official");
    expect([run.approval, phaseOf(run)]).toEqual(["waiting", "plan"]);
    run = applyEvent(applyEvent(run, { type: "approval", state: "approved" }), { type: "plan", goal: "g" });
    expect(phaseOf(run)).toBe("explore");
  });

  it("a run that ends while the plan waits is no longer waiting", () => {
    const run = applyEvent(applyEvent(emptyRun, { type: "approval", state: "waiting" }), { type: "finished", status: "cancelled", items: 0 });
    expect(run.approval).toBe("");
  });
});

suite("team", () => {
  it("tracks sub-agents, their files, the brain's verdict, the result check and which browser is shown", () => {
    let run = applyEvent(emptyRun, { type: "agent", agent: "a1", name: "Scout 1", status: "running", url: "https://uni.example/s" });
    run = applyEvent(run, { type: "agent", agent: "a2", name: "Scout 2", status: "running", url: "https://copy.example" });
    run = applyEvent(run, { type: "focus", agent: "a1" });
    run = applyEvent(run, { type: "file", agent: "a1", name: "syllabus.pdf", url: "https://uni.example/s.pdf", size: 1200, content_type: "application/pdf" });
    run = applyEvent(run, { type: "verify", agent: "a1", complete: true, why: "official syllabus" });
    run = applyEvent(run, { type: "result_check", agent: "a1", name: "Scout 1", items: 0, files: ["syllabus.pdf"], why: "official syllabus" });
    run = applyEvent(run, { type: "approval", state: "waiting", topic: "result" });
    expect(run.focus).toBe("a1");
    expect(run.files[0]).toMatchObject({ name: "syllabus.pdf", agent: "a1", size: 1200 });
    expect(run.agents.find((a) => a.id === "a1")?.verdict).toBe("✓ official syllabus");
    expect(run.resultCheck).toMatchObject({ name: "Scout 1", state: "waiting", files: ["syllabus.pdf"], doubt: false });
    expect(applyEvent(emptyRun, { type: "result_check", agent: "a2", name: "Scout 2", items: 101, files: [], why: "cannot confirm the total", doubt: true }).resultCheck?.doubt).toBe(true);
    expect(run.approval).toBe(""); // a result check is not a plan approval
    run = applyEvent(run, { type: "approval", state: "approved", topic: "result" });
    expect(run.resultCheck?.state).toBe("approved");
    run = applyEvent(run, { type: "finished", status: "completed", items: 0 });
    expect(run.agents.map((a) => a.status)).toEqual(["done", "stopped", "stopped"]); // the brain is done; sub-agents still going were stopped
  });
});

suite("human in the loop", () => {
  it("shows who needs a person until the browser goes back to the agent", () => {
    let run = applyEvent(emptyRun, { type: "help_needed", agent: "a2", host: "www.google.com", url: "https://www.google.com/sorry/index" });
    expect(run.help).toEqual({ agent: "a2", host: "www.google.com", url: "https://www.google.com/sorry/index" });
    run = applyEvent(run, { type: "control", mode: "requested" });
    run = applyEvent(run, { type: "control", mode: "user" });
    expect(run.help).not.toBeNull(); // still waiting while the person drives
    expect(applyEvent(run, { type: "control", mode: "agent" }).help).toBeNull();
    expect(applyEvent(run, { type: "help_done", host: "www.google.com" }).help).toBeNull();
    expect(applyEvent(run, { type: "finished", status: "cancelled", items: 0 }).help).toBeNull();
  });
});
