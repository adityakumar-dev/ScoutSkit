## **PROJECT SYNOPSIS** 

# **INVISIBLE FAILURE** 

### **An Autonomous Web Task Execution and Evaluation Platform for RealWorld Functional, Usability and Accessibility Testing** 

Submitted in partial fulfilment of the requirements for the degree of 

### **Bachelor of Technology (B.Tech.)** 

in 

### **Computer Science and Engineering** 



<!-- Start of picture text -->
SsANICAL UNIysRy,<br>GeSG2005 P28<br>Kye NO<br>Sef / SXaN~<br>A<br>oK|<br>Nee,<br><!-- End of picture text -->

#### **Department of Computer Science and Engineering Faculty of Technology** 

#### **Uttarakhand Technical University, Dehradun** 

Academic Session: 2026–2027 

#### **Submitted to:** 

Dr. Shailesh Singh Panwar 

**Submitted by:** 

Aditya Kumar 740000101002 Pratiksha Topwal 

230000101071 

### **1. Introduction** 

Websites are usually built and tested on fast connections, modern devices and English interfaces. In India, many citizens use government portals, university websites and smallbusiness services over slow or unstable mobile networks, on low-end phones, in Hindi or other regional languages, and sometimes with assistive technology. A website that works for its developer can still fail for these users: a form may give no feedback while loading, a button may be pressed twice, typed data may be lost when the connection drops, Devanagari text may overflow, or a task may be impossible to finish with a keyboard alone. Developers rarely see these failures because they never experience them. 

Invisible Failure is an autonomous web interaction and evaluation platform. It understands natural-language instructions, plans tasks, interacts with websites through browser automation, completes user workflows, and evaluates the website experience. It does not only ask whether a website works. It asks whether a particular user can complete a particular task, conveniently, under particular conditions. The platform has two operating modes: 

1. **Mode 1, Autonomous Task Execution:** a general browser task system. The user gives an instruction such as "visit a hackathon website, extract all problem statements with their numbers, titles and descriptions, categorise them and generate a CSV file". The system plans subtasks, navigates and extracts, validates the outcome and produces the output with logs and evidence. 

2. **Mode 2, Automated Website Testing and Evaluation:** the same engine runs a workflow, supplied by the user or discovered automatically, under different environments, for example "check whether a student can find and download an examination result on a low-end phone with an unstable connection". It evaluates functional correctness, usability and accessibility. 

Two ideas shape the design. The first is to explore once and replay many times: a workflow is explored a single time and compiled into a recipe of action intents, element locators, expected page states and expected outcomes, which can then be replayed under different conditions. This keeps the steps identical, so that the only variable is the condition, and it reduces repeated AI planning. The second is hierarchical, parallel agents: an orchestrator divides the work, run agents execute workflows in isolated browser sessions, and replay agents investigate failures by changing one condition at a time. 

1 

### **2. Problem Statement** 

Functional testing, usability evaluation and accessibility testing are usually done separately, by different tools, along paths a tester has already scripted and under ideal conditions. A website can pass each of them and still fail for a user on a slow network, an old device, a regionallanguage interface or with assistive technology. Such tools report that something failed but rarely explain which step and which condition caused it, and testing one workflow across many combinations of persona, network, device and language step by step is slow. There is a need for a platform that can execute tasks and workflows autonomously on websites, run them under configurable real-world conditions in parallel, evaluate all three dimensions together, and produce reproducible evidence of every failure and its likely trigger. 

### **3. Objectives** 

The central research question is: can an autonomous browser agent execute website workflows and systematically evaluate their functional correctness, usability and accessibility across different user personas and simulated real-world environments, while producing reproducible evidence of failures? A related question is whether parallel recipe replay gives findings equivalent to sequential execution with reduced evaluation time. The objectives are: 

1. To plan natural-language tasks into subtasks with expected completion conditions, execute them through structured browser tools, maintain execution state, validate outcomes and generate the requested output (Mode 1). 

2. To build a controlled browser interaction engine on Playwright with bounded tools and a structured record of every action. 

3. To explore a workflow once and compile it into a reusable recipe, and to replay it under different conditions. 

4. To discover candidate workflows on a website automatically and let the user select them for execution or testing. 

5. To evaluate functional correctness, task-based usability and accessibility (Mode 2), including a task-difficulty metric built from measurable interaction data and validated experimentally. 

6. To provide predefined and custom environment profiles covering network, processing, display, language and interaction mode. 

7. To build a hierarchical orchestrator with run agents and replay agents that execute in 

2 

parallel in isolated sessions with a concurrency cap, and to localise failures by changing one condition at a time. 

8. To evaluate the system on controlled benchmark websites with known faults, compare parallel with sequential results, and compare corresponding components with existing tools. 

### **4. Literature Review** 

This review covers research related to autonomous web agents, web crawling and testing, usability and accessibility evaluation, network emulation, failure localisation and reproducible testing. Each paper was checked against its publisher or bibliographic record (title, authors, year, venue and DOI where one exists). Older papers are cited for the ideas they established. The tools this project will use are listed in Chapter 6, with their maintenance status checked in October 2026. 

#### **4.1 Web agents, crawling and testing** 

WebArena [13] provides a self-hostable environment of fully functional websites and a benchmark of 812 long-horizon tasks that map natural-language intents to web interactions. Tasks are judged by the functional correctness of the outcome, and the agents tested fell far below human performance. This motivates outcome validation and reproducibility in Mode 1. The Crawljax approach [10] crawls Ajax applications by analysing DOM changes in the browser and inferring a state-flow graph of interface states, and Mesbah, van Deursen and Roest [11] use it for invariant-based testing that detects Ajax-specific faults with DOM-tree invariants as oracles. These works show that dynamic exploration can find faults without handwritten scripts, which supports workflow discovery and functional testing. 

#### **4.2 Usability and accessibility evaluation** 

Ivory and Hearst [8] survey the automation of usability evaluation and propose a taxonomy; they describe it as underexplored. Their work supports measurable, task-based indicators over subjective scoring alone. Vigo, Brown and Conway [9] compared six automated accessibility tools with expert evaluation against WCAG 2.0 and found that the tools covered at most about half of the success criteria, concluding that automated tests need to be complemented by expert evaluation and user testing. This project therefore combines axe-core with interaction tests and separates automated findings from issues needing manual review. 

3 

#### **4.3 Network emulation, failure localisation and reproducibility** 

Mahimahi [14] records HTTP traffic and replays it under emulated network conditions, showing the value of controlled, repeatable conditions for web measurement. This project uses the emulation built into the browser instead of a separate tool. Zeller and Hildebrandt [12] introduce Delta Debugging, which simplifies a failing test case and isolates the difference between passing and failing runs; in one case a browser crash after 95 user actions was reduced to three actions. The recipe replay in this project follows the same principle of repeatable runs with controlled differences, applied to environmental conditions. 

#### **4.4 Existing tools and current AI testing tools** 

|**Tool**|**What it does well**|**Limitation relevant to this**<br>**project**|
|---|---|---|
|Lighthouse [4]|Audits performance,<br>accessibility and best practices<br>of a page; recent versions add an<br>agentic-browsing category|Page-level audit under one<br>profile; does not execute multi-<br>step workflows or compare<br>personas|
|axe-core [3]|Detects rule-based accessibility<br>violations against WCAG [1]|Checks a page state; does not<br>observe behaviour under degraded<br>conditions or measure task<br>difficulty|
|Playwright [2] and<br>Selenium [6]|Run scripted workflows with<br>network throttling|Need hand-written scripts; do not<br>explain the cause of a failure|
|Playwright MCP<br>and test agents [2],<br>[7]|Let AI agents control a real<br>browser through structured tools;<br>planner, generator and healer<br>agents create and repair tests<br>(documented for the Node.js<br>version; to be confirmed)|Aimed at generating and repairing<br>functional tests; do not evaluate<br>usability or accessibility across<br>personas and simulated<br>environments|



Stagehand [5] is an MIT-licensed SDK, available for TypeScript and Python, that adds naturallanguage act, observe and extract calls on top of browser automation, and it is actively released (version 4 in August 2026). Browser-use is a Python agent framework in which the model decides each step. This project plans to use Stagehand for exploration only, and to replay compiled recipes with plain Playwright locators so that the steps stay identical between runs. Because tools in this area change quickly, the choice between Stagehand and browser-use will be confirmed in a short trial at the start of the project. 

4 

#### **4.5 Research gap** 

In the sources reviewed, autonomous task execution, workflow discovery, functional testing, usability measurement, accessibility checking and environment simulation appear mostly as separate lines of work. This project studies them in one integrated platform and uses parallel recipe replay for condition-based testing and failure localisation. The recipe idea is related to test generation and self-healing in the Playwright test agents and to record-and-replay tools; here it serves mainly as a controlled instrument for repeating a workflow under changed conditions. It does not claim that no similar system exists, and the gap statement will be rechecked against further literature before the final report. 

### **5. Proposed Methodology** 

#### **5.1 System architecture** 

The architecture has three levels of agents (Figure 1). Planning and browser execution are kept separate: the orchestrator and agents decide what to do, and a shared browser layer carries it out through bounded tools. All planned components below are proposed work; none is claimed as already implemented. 

5 



<!-- Start of picture text -->
Mode 1: Task Mode 2: Website Personas and environments<br>atural-tanguage instruction URL, task test or discover predefined or custom<br>Main Brain (Orchestrator)<br>plans the task and subtasks; selects discovered workflows; builds the persona and environment matrix;<br>Level 1 Run Agent 1 Level 1 Run Agent 2 Level 1 Run Agent N<br>one workflow, one persona: one workflow, one persona one workflow, one persona<br>Isolated browse session Isolated browse session Inolated browse session<br>Functional Testing Usability Evaluation Accessibility Evaluation<br>broken flows, fled requests, ‘completion, time, steps, axe-core, keyboard, focus,<br>Jost data, duplicate submis backracking, failed attempts 200m, Devanagari rendering<br>Level 2 Replay Agents H Shared services 1 |2<br>CIE DOCTOR ERD H Paererene apeianl antec ere i |e<br>With exactly one condition changed H store, workflow discovery, environments i ie<br>Evidence, Failure Localization and Reporting <1<br>logs, screenshots, traces, network records, fled step, suggested improvements<br>Dashboard and API Execution records<br>FastAPI; web dashboard SQLite; screenshots, traces<br>Ly component [7 certs nt wen tre oun 777 supporting services<br><!-- End of picture text -->

_Figure 1: Proposed system architecture_ 

#### **5.2 Operating modes** 

In Mode 1 the planner turns an instruction into a structured plan with subtasks and expected completion conditions, keeps task state during execution, uses browser tools to navigate, click, scroll, fill forms and extract information, validates the result against the completion conditions, and writes the requested output (for example a CSV file) with logs and screenshots. In Mode 2 the user supplies a website and a task to test, or asks the system to discover workflows. The engine explores once, compiles the recipe, and replays it under the selected environments while evaluating the three dimensions. Both modes share the same planner, browser tools and recipe engine. 

6 

#### **5.3 Components** 

|**Component**|**Function**|
|---|---|
|Main Brain<br>(Orchestrator)|Plans the task and subtasks, selects workflows, builds the<br>persona and environment matrix, assigns runs to agents,<br>enforces budget and a per-website concurrency cap, and<br>merges results. It uses ordinary Python concurrency (asyncio<br>with a limited pool of browser sessions); a language model is<br>used for planning and exploration only.|
|Level 1 Run Agents|Each executes one workflow as one persona in its own isolated<br>browser session, records evidence and runs the evaluations.|
|Level 2 Replay Agents|Created only on failure. Each replays the recipe with exactly<br>one condition changed (network, CPU, language, screen size,<br>input mode) to find which condition triggers the failure. Depth<br>and number of child agents are capped.|
|Browser interaction tools|Structured Playwright tools instead of arbitrary generated<br>scripts: inspect DOM and accessibility tree, navigate, click, fill,<br>select, scroll, keyboard actions, resize viewport, screenshots,<br>network events, page state and outcome validation. Every<br>action is recorded. Exploration may use Stagehand; compiled<br>recipes are replayed with plain Playwright locators and no<br>language model.|
|Recipe engine|Compiles an explored workflow into a recipe holding action<br>intent, element locator (role, label, text), expected page state,<br>expected outcome and execution sequence. Approved recipes<br>are never overwritten; changes are stored as new candidate<br>versions.|
|Workflow discovery|Explores navigation, links, forms, search interfaces and<br>downloads to propose candidate workflows (for example<br>finding examination results, downloading academic documents,<br>searching admission notices). They are only candidates; the<br>user selects which to run.|
|Functional testing|Checks broken links and navigation, form validation, button<br>behaviour, failed requests, page errors, duplicate submissions,<br>lost data, workflow failures and recovery after network<br>interruption, against expected outcomes. It does not claim to<br>verify business rules without specifications.|



7 

|**Component**|**Function**|
|---|---|
|Usability evaluation|Measures completion rate, time, interaction steps, failed<br>attempts, backtracking, repeated interactions, error recovery<br>and abandonment, and compares tasks across websites,<br>personas and environments.|
|Accessibility evaluation|Checks accessible labels, keyboard navigation, focus visibility<br>and order, image descriptions, colour contrast, heading<br>structure, form accessibility, zoom and text scaling,<br>accessibility-tree information and Hindi or Devanagari<br>rendering, using axe-core and interaction tests with WCAG 2.2<br>as reference. WCAG 3.0 is still a working draft, so WCAG 2.2<br>remains the current Recommendation.|
|Evidence and reporting|Stores execution history, timestamped logs, screenshots, traces,<br>network records, results, the failed step, the environment<br>configuration and suggested improvements.|



#### **5.4 Environment simulation and personas** 

Each agent runs in its own browser context with its own viewport, language and offline setting. Network speed and processor slowdown are applied through a Chromium DevTools Protocol session attached to each page, which Playwright supports for Chromium (CPU throttling is Chromium-only). Whether the throttling stays independent between parallel sessions, and whether it also applies to pages driven through Stagehand, will be tested at the start of the project. Simulated conditions are not the same as testing on physical devices, and reports will say so. 

|**Group**|**Configurable parameters**|
|---|---|
|Network|Bandwidth, latency, jitter, packet loss where supported, offline<br>mode, mid-request disconnection|
|Processing|CPU slowdown and processing constraints|
|Display|Viewport size; mobile, tablet and desktop; zoom and text scaling|
|Language and<br>interaction|English and Hindi; regional-language interfaces; mouse; keyboard<br>only; slower interaction|



Predefined profiles include high-end desktop, average mobile, low-end mobile, slow network, unstable network, keyboard-only and Hindi-language, and users can build custom combinations. Personas are configurable combinations of these conditions, for example a rural 

8 

mobile user (low bandwidth, unstable network, limited processing), an elderly user (enlarged text, zoom, slower interaction), a Hindi-only user, a keyboard-only user and a screen-reader user. 

#### **5.5 Workflow of a test run** 

Figure 2 shows how a job proceeds. If a failure is detected, replay agents repeat the recipe with one condition changed each, in parallel, to find the likely trigger. 



<!-- Start of picture text -->
1. Input 2. Plan 3. Explore once 4. Compile recipe<br>taskorwebsi, |] subtasks, workflows, |—®} records the steps. |} intent, locators,<br>‘mode, environments persona matrix taken expected outcome<br>7. Failure 6. Validate, evaluate 5. Replay in parallel<br>pares +—] outcome; functional, }—} isolated sessions,<br>usability, access, capped number<br>| " \<br>8. Replay agents 9. Output, report<br>change one condition |——®] task output (Mode 1),<br>ata time evidence (Mode 2)<br>Explore once, replay many times: the steps stay identical and only the conditions change.<br><!-- End of picture text -->

_Figure 2: Workflow of a run_ 

#### **5.6 Parallel execution and usability metric** 

Running many browsers on one computer can distort measurements, because agents compete for processor and network capacity. The project therefore uses a fixed concurrency limit, records the load during each run, and checks whether parallel and sequential execution report equivalent findings, with the time saved reported. On real websites the number of simultaneous agents per website is capped, with delays between actions, so testing does not behave like load testing. 

For usability, completion, time, interaction count, failed attempts and backtracking are normalised, for example against the shortest known path or a baseline environment, and combined into a task-difficulty indicator. Weights are not assumed. They will be tested against ratings given by volunteers who attempt the same tasks, and the indicator will not be presented as an established standard. 

9 

#### **5.7 Experimental evaluation** 

Controlled benchmark websites with known characteristics and deliberately introduced faults will be built, and a field study of public government and university websites will be run nonintrusively, with findings verified manually. Components that correspond to existing tools will be compared with Lighthouse, axe-core and manually scripted Playwright workflows. No superiority is claimed before results exist. 

|**Area**|**Measures**|
|---|---|
|Task execution|Planning accuracy, browser action success rate, task completion<br>accuracy, recovery from failed interactions, recipe replay success,<br>reproducibility|
|Functional|Failure detection accuracy, false-positive rate, detection of broken<br>workflows|
|Usability|Completion rate and time, interaction count, backtracking, failed<br>attempts|
|Accessibility|Violations found, keyboard workflow completion, detection of<br>injected faults|
|Environment and<br>localisation|Performance across profiles; accuracy of the identified triggering<br>condition on faults with known cause|
|Parallel execution|Time saved against sequential runs; equivalence of findings|



#### **5.8 Scope of the first working demonstration (40%)** 

The module shown after 20/11/2026 will use controlled demonstration websites and include: natural-language task input and basic decomposition; controlled browser execution with DOM and accessibility-tree inspection; recording and replay of a user-provided task as a recipe; an orchestrator running several agents in parallel in isolated sessions; at least three environment profiles; basic functional testing and usability metrics; axe-core integration and keyboard checks; and screenshots, structured logs and a unified initial report. Automatic workflow discovery, replay agents for failure localisation, complex environment combinations and expanded benchmarking continue in the 8th semester. 

#### **5.9 Ethical and safety considerations** 

- Public websites are tested non-intrusively. No real applications, payments or sensitive forms are submitted, and robots.txt and access policies are respected. 

- No load testing is done without authorisation, and the number of agents per website is 

10 

capped. Interrupted-request and destructive scenarios run only on controlled websites. 

- Navigation is restricted through allowlists and validation, sensitive actions need confirmation, and only necessary evidence is stored. 

- Automated testing is not claimed to establish full WCAG compliance. 

### **6. System Requirements** 

#### **6.1 Hardware requirements** 

|**Component**|**Requirement**|
|---|---|
|Computer|Laptop or desktop with a multi-core processor (Intel Core i5<br>or equivalent)|
|Memory|8 GB RAM minimum; 16 GB recommended because<br>several browser sessions run in parallel|
|Storage|30 GB free disk space for browsers, containers, traces,<br>screenshots and data|
|Network|Internet connection for language-model access and public-<br>site scans|



#### **6.2 Software requirements** 

Maintenance status of the main tools was checked against their release records in October 2026. 

|**Component**|**Requirement**|**Status checked (Oct 2026)**|
|---|---|---|
|Operating system|Windows 10/11 or Linux|-|
|Languages|Python 3.12 or later (asyncio for<br>parallel agents); JavaScript for in-page<br>checks|Python 3.10 reaches end of<br>support in 2026|
|Browser<br>automation|Playwright with Chromium|Actively released (1.64, Oct<br>2026)|
|Accessibility<br>testing|axe-core|Actively released (4.14, Oct<br>2026)|
|Exploration agent|Stagehand (Python SDK), version<br>pinned|Actively released (v4, Aug<br>2026); API changes between<br>major versions|
|Backend|FastAPI [15], Uvicorn|Actively released (FastAPI<br>0.136, Uvicorn 0.48 in 2026)|



11 

|**Component**|**Requirement**|**Status checked (Oct 2026)**|
|---|---|---|
|Validation|Schema validation library such as<br>Pydantic for plans, recipes and model<br>output|-|
|Baseline tools|Lighthouse, scripted Playwright,<br>Selenium (for comparison)|Lighthouse 13.x and<br>Selenium 4.52 actively<br>released|
|Data storage|SQLite (PostgreSQL if needed)|Mature, widely used|
|Dashboard|Simple web dashboard; framework to<br>be decided|-|
|Language model<br>and retrieval|Configurable cloud provider or local<br>model; no model fixed; embeddings<br>and RAG where useful; deterministic<br>mock or local mode for reproducible<br>demonstrations|Vendor-independent by<br>design|
|Test environments|Docker for controlled benchmark<br>websites|Mature, widely used|
|Development tools|Visual Studio Code, Git|Mature, widely used|
|Other technologies<br>(to be finalised<br>with the guide)|[Space for additional tools or<br>libraries]||



Versions will be pinned at the start of implementation and rechecked before the final submission, because these tools update frequently. 

Python is chosen for team familiarity, for its strong support for statistical analysis of the experimental results, and because Playwright for Python provides the browser controls the project needs, including DevTools Protocol sessions for network and CPU throttling. axe-core is a JavaScript library and is injected into the page from Python. Language-model output is validated against schemas before it is used. 

### **7. Project Timeline** 

The synopsis is due on 31/10/2026 and the 40% working module is presented after 20/11/2026. Dates in the 8th semester are estimates and will be adjusted to the department schedule. 

12 

|**No.**|**Activity**|**Estimated completion**|
|---|---|---|
|1|Synopsis submission to Dr. Shailesh Singh Panwar|31/10/2026|
|2|Literature review including current AI browser and<br>testing tools; trial Stagehand and test per-session<br>network and CPU throttling in parallel Playwright<br>sessions, including pages driven through Stagehand;<br>pin tool versions; finalise requirements|07/11/2026|
|3|Task input and planning, controlled browser tools,<br>DOM and accessibility-tree inspection, recipe<br>recording and replay|14/11/2026|
|4|Orchestrator with parallel isolated sessions; three<br>environment profiles; basic functional testing and<br>usability metrics; axe-core and keyboard checks;<br>demonstration websites|18/11/2026|
|5|Screenshots, logs and unified initial report; preparation<br>of the 40% demonstration|20/11/2026|
|6|Presentation of working module (40%)|After 20/11/2026|
|7|Automatic workflow discovery; extension of Mode 1<br>to multi-page extraction and output generation|January 2027|
|8|Custom environments, persona combinations, mid-<br>request disconnection|February 2027|
|9|Level 2 replay agents for failure localisation; Hindi<br>and Devanagari checks|March 2027|
|10|Benchmark completion, parallel versus sequential<br>comparison, full evaluation against Lighthouse, axe-<br>core and scripted Playwright|April 2027|
|11|Final report, paper draft and submission|End of 8th semester|



### **8. References** 

- [1] World Wide Web Consortium (W3C), "Web Content Accessibility Guidelines (WCAG) 2.2," W3C Recommendation. [Online]. Available: https://www.w3.org/TR/WCAG22/ 

- [2] Microsoft, "Playwright documentation." [Online]. Available: https://playwright.dev 

- [3] Deque Systems, "axe-core." [Online]. Available: https://github.com/dequelabs/axe-core 

- [4] Google, "Lighthouse." [Online]. Available: https://developer.chrome.com/docs/lighthouse 

- [5] Browserbase, "Stagehand," GitHub repository. [Online]. Available: 

13 

https://github.com/browserbase/stagehand 

- [6] Selenium Project, "Selenium documentation." [Online]. Available: https://www.selenium.dev 

- [7] Microsoft, "Playwright MCP," GitHub repository. [Online]. Available: https://github.com/microsoft/playwright-mcp 

- [8] M. Y. Ivory and M. A. Hearst, "The state of the art in automating usability evaluation of user interfaces," ACM Computing Surveys, vol. 33, no. 4, pp. 470–516, Dec. 2001, doi: 10.1145/503112.503114. 

- [9] M. Vigo, J. Brown, and V. Conway, "Benchmarking web accessibility evaluation tools: Measuring the harm of sole reliance on automated tests," in Proc. 10th Int. CrossDisciplinary Conf. on Web Accessibility (W4A '13), Rio de Janeiro, Brazil, May 2013, Art. no. 1, doi: 10.1145/2461121.2461124. 

- [10] A. Mesbah, A. van Deursen, and S. Lenselink, "Crawling Ajax-based web applications through dynamic analysis of user interface state changes," ACM Trans. Web, vol. 6, no. 1, Art. 3, Mar. 2012, doi: 10.1145/2109205.2109208. 

- [11] A. Mesbah, A. van Deursen, and D. Roest, "Invariant-based automatic testing of modern web applications," IEEE Trans. Softw. Eng., vol. 38, no. 1, pp. 35–53, Jan./Feb. 2012, doi: 10.1109/TSE.2011.28. 

- [12] A. Zeller and R. Hildebrandt, "Simplifying and isolating failure-inducing input," IEEE Trans. Softw. Eng., vol. 28, no. 2, pp. 183–200, Feb. 2002, doi: 10.1109/32.988498. 

- [13] S. Zhou et al., "WebArena: A realistic web environment for building autonomous agents," arXiv:2307.13854, 2023 (rev. Apr. 2024), doi: 10.48550/arXiv.2307.13854. 

- [14] R. Netravali, A. Sivaraman, S. Das, A. Goyal, K. Winstein, J. Mickens, and H. Balakrishnan, "Mahimahi: Accurate record-and-replay for HTTP," in Proc. 2015 USENIX Annual Technical Conf. (USENIX ATC 15), Santa Clara, CA, USA, Jul. 2015, pp. 417–429. 

- [15] S. Ramírez, "FastAPI documentation." [Online]. Available: https://fastapi.tiangolo.com 

14 

