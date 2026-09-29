const REPO_ROOT = "https://github.com/KaituoZhang/AsynCodeBench";
const REPO = `${REPO_ROOT}/tree/main`;
const REPO_FILE = path => `${REPO_ROOT}/blob/main/${path}`;
const PAPER_URL = "https://arxiv.org/abs/2609.32662";
const PAPER_PDF = "https://arxiv.org/pdf/2609.32662";
const BIBTEX = `@misc{zhang2026asyncodebenchbenchmarkingcollaborationasynchronous,
  title={AsynCodeBench: Benchmarking Collaboration of Asynchronous Multi-Agent Systems in Software Engineering},
  author={Kaituo Zhang and Zhen Xiong and Zhimeng Jiang and Mingyu Zhong and Zhouyuan Yuan and Zhecheng Li and Bowen Lin and Chia-Yuan Chang and Mingzhi Hu and Huazheng Wang and Ying Lin},
  year={2026},
  eprint={2609.32662},
  archivePrefix={arXiv},
  primaryClass={cs.SE},
  url={https://arxiv.org/abs/2609.32662},
}`;

const TASKS = [
  { id:"cachetools", project:"cachetools", domain:"Caching", nodes:4, deps:5, agents:2, summary:"Implement cache key construction and decorator factories while preserving typed keys, metadata, limits, and lock semantics." },
  { id:"deprecated", project:"Deprecated", domain:"Decorators", nodes:3, deps:3, agents:2, summary:"Coordinate classic and Sphinx-aware deprecation decorators across shared warning and documentation behavior." },
  { id:"portalocker", project:"portalocker", domain:"File locking", nodes:3, deps:3, agents:2, summary:"Complete platform backends and high-level locking utilities without breaking cross-platform state and cleanup contracts." },
  { id:"tinydb", project:"TinyDB", domain:"Database", nodes:3, deps:3, agents:2, summary:"Reconnect query construction with table state and integration behavior in a compact document database." },
  { id:"wcwidth", project:"wcwidth", domain:"Unicode", nodes:3, deps:2, agents:2, summary:"Implement Unicode version selection and terminal width behavior under a shared public compatibility contract." },
  { id:"requests", project:"Requests", domain:"HTTP", nodes:3, deps:3, agents:3, summary:"Align prepared requests, transport adapters, and integration behavior across redirects, bodies, headers, and connection flow." },
  { id:"simpy", project:"SimPy", domain:"Simulation", nodes:4, deps:3, agents:4, summary:"Implement event, environment, resource, and realtime utilities whose scheduling contracts cross module boundaries." },
  { id:"parsel", project:"Parsel", domain:"Parsing", nodes:3, deps:2, agents:3, summary:"Coordinate CSS translation, XPath utilities, and selector behavior so queries preserve the same observable semantics." },
  { id:"filesystem_spec", project:"fsspec", domain:"Filesystems", nodes:3, deps:2, agents:3, summary:"Complete filesystem core, registry, and utility behavior around protocol discovery and shared path conventions." },
  { id:"marshmallow", project:"marshmallow", domain:"Serialization", nodes:3, deps:3, agents:3, summary:"Connect field behavior, class registry, and schema loading while preserving nested serialization contracts." },
  { id:"imapclient", project:"IMAPClient", domain:"Email", nodes:3, deps:3, agents:3, summary:"Join lexer and parsing utilities with the client API so wire responses become stable high-level values." },
  { id:"pexpect", project:"Pexpect", domain:"Processes", nodes:4, deps:3, agents:4, summary:"Implement process transport, spawn, expect, and wrapper behavior across timing and stream-boundary contracts." },
  { id:"flask", project:"Flask", domain:"Web framework", nodes:4, deps:3, agents:4, summary:"Coordinate dispatch, sessions, templates, testing, and scaffolding behavior in a real web framework codebase." },
  { id:"python-rsa", project:"Python-RSA", domain:"Cryptography", nodes:4, deps:3, agents:4, summary:"Connect arithmetic, keys, PKCS#1 operations, and serialization under strict cryptographic data contracts." },
  { id:"cookiecutter", project:"Cookiecutter", domain:"Code generation", nodes:4, deps:3, agents:4, summary:"Coordinate source discovery, prompts, configuration, generation, and orchestration in a template-based CLI workflow." },
  { id:"apache-tvm-20018", project:"Apache TVM", domain:"Compiler", nodes:3, deps:2, agents:3, summary:"Repair return handling across core IR, backend behavior, and script-level rendering in a compiler stack." },
  { id:"apache-tvm-20073", project:"Apache TVM", domain:"Compiler", nodes:3, deps:2, agents:3, summary:"Align IRBuilder propagation with source mapping so generated compiler IR retains correct structural provenance." },
  { id:"apache-tvm-20107", project:"Apache TVM", domain:"Compiler", nodes:3, deps:2, agents:3, summary:"Coordinate script core, Relax, and TIRx parsing behavior across dialect boundaries." },
  { id:"apache-tvm-20153", project:"Apache TVM", domain:"Compiler", nodes:3, deps:2, agents:3, summary:"Connect dialect definitions, lowering, and rendering while preserving compiler syntax and transformation contracts." }
];

const CATEGORIES = [
  { name:"Framework and libraries", tasks:["cachetools","deprecated","parsel","marshmallow","flask","cookiecutter"] },
  { name:"Systems and storage", tasks:["portalocker","tinydb","wcwidth","simpy","filesystem_spec","pexpect"] },
  { name:"Compiler and IR", tasks:["apache-tvm-20018","apache-tvm-20073","apache-tvm-20107","apache-tvm-20153"] },
  { name:"Network protocols", tasks:["requests","imapclient"] },
  { name:"Security", tasks:["python-rsa"] }
];
CATEGORIES.forEach(category => {
  category.count = category.tasks.length;
  category.percentage = `${Math.round((category.count / TASKS.length) * 100)}%`;
  category.tasks.forEach(id => {
    const task = TASKS.find(item => item.id === id);
    if (task) task.category = category.name;
  });
});

const PROTOCOLS = [
  ["single", "Single agent", "One iterative agent owns the complete task."],
  ["serial_specialists", "Serial specialists", "Specialists run in dependency order with completed upstream handoffs."],
  ["async_private", "Async private", "Specialists run concurrently from private workspaces without in-flight communication."],
  ["caid_manager", "Async-Read Only-Manager", "A read-only manager coordinates private-worktree specialists under validated delegation and scope rules."],
  ["async_manager", "Async-Manager", "A persistent manager observes integration checkpoints and may submit validated, scope-constrained production patches."]
];

const copyBlock = (text, lang="bash") => `<div class="code-wrap"><pre><code class="language-${lang}">${escapeHtml(text.replaceAll("\n+", "\n"))}</code></pre><button class="copy" data-copy>Copy</button></div>`;
const escapeHtml = value => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const header = current => `<a class="skip-link" href="#main">Skip to content</a><header class="site-header"><div class="container nav"><a class="brand" href="/"><span class="brand-mark">A↗</span><span>AsynCodeBench</span></a><nav class="nav-links" aria-label="Primary"><a href="/" ${current==="home"?'aria-current="page"':''}>Overview</a><a href="/run/" ${current==="run"?'aria-current="page"':''}>Quick Run</a><a href="${PAPER_URL}" target="_blank" rel="noreferrer">Paper</a><a href="${REPO}" target="_blank" rel="noreferrer">GitHub</a><a class="nav-task" href="/tasks/" ${current==="tasks"?'aria-current="page"':''}>Explore ${TASKS.length} tasks</a><a class="nav-cta" href="/run/">Run a task →</a></nav></div></header>`;
const footer = () => `<footer class="site-footer"><div class="container footer-row"><span>AsynCodeBench · Dependency-aware asynchronous coding evaluation</span><span><a href="${PAPER_URL}" target="_blank" rel="noreferrer">Paper</a> · <a href="#citation">BibTeX</a> · <a href="${REPO_FILE("LICENSE")}">Apache-2.0</a> · <a href="${REPO_ROOT}/graphs/contributors">Contributors</a></span></div></footer>`;

function home() {
  document.title = "AsynCodeBench — Evaluate asynchronous coding agents";
  document.body.innerHTML = `${header("home")}<main id="main">
    <section class="hero"><div class="container">
      <span class="eyebrow">Dependency-aware coding benchmark</span>
      <h1>Can coding agents work <em>together</em>?</h1>
      <p class="hero-copy">Passing tests is only the end state. AsynCodeBench reveals whether asynchronous agents discover, communicate, and resolve the software dependencies between their private workspaces.</p>
      <div class="hero-actions"><a class="button primary" href="/run/">Run your first task →</a><a class="button" href="/tasks/">Explore ${TASKS.length} tasks</a><a class="button" href="${REPO}" target="_blank" rel="noreferrer">View on GitHub ↗</a></div>
      <div class="proof-strip"><div class="proof"><strong>${TASKS.length}</strong><span>repository-level tasks</span></div><div class="proof"><strong>${PROTOCOLS.length}</strong><span>controlled protocols</span></div><div class="proof"><strong>${TASKS.length * PROTOCOLS.length}</strong><span>task–protocol conditions</span></div><div class="proof"><strong>${TASKS.reduce((sum, task) => sum + task.deps, 0)}</strong><span>executable dependencies</span></div></div>
    </div></section>
    <section class="section alt"><div class="container"><div class="section-head"><span class="section-kicker">The missing signal</span><div><h2>A correct patch can hide a broken team.</h2><p class="section-lede">Most coding benchmarks grade only the final repository. That cannot tell us whether parallel work was actually coordinated—or whether an integrator merely repaired incompatible changes at the end.</p></div></div>
      <div class="cards"><article class="card"><span class="card-num">01</span><h3>Tests miss the process</h3><p>Final pass rate says what survived integration, not when cross-agent assumptions became compatible.</p></article><article class="card"><span class="card-num">02</span><h3>Parallelism creates stale state</h3><p>Private workspaces make interfaces, data formats, and shared invariants easy to violate without visibility.</p></article><article class="card"><span class="card-num">03</span><h3>Coordination has a cost</h3><p>Speed, tokens, failed attempts, scope violations, and recovery all matter alongside correctness.</p></article></div>
    </div></section>
    <section class="section"><div class="container"><div class="section-head"><span class="section-kicker">Controlled comparison</span><div><h2>Same task. Same decomposition. Five ways to work.</h2><p class="section-lede">Each protocol changes execution, information flow, or manager write authority while keeping the underlying software task fixed.</p></div></div><div class="protocol-grid">${PROTOCOLS.map((p,i)=>`<article class="protocol"><code>0${i+1} / ${p[0]}</code><h3>${p[1]}</h3><p>${p[2]}</p></article>`).join("")}</div></div></section>
    <section class="section alt"><div class="container"><div class="section-head"><span class="section-kicker">Two collaboration metrics</span><div><h2>Measure whether dependencies resolve—and when.</h2><p class="section-lede">For dependency <em>d</em> at integration checkpoint <em>t</em>, <strong>I<sub>d,t</sub> ∈ {0,1}</strong> records whether its integrated Dependency Checker passes. The trajectory across checkpoints makes collaboration observable beyond the final test result.</p></div></div><div class="metric-grid"><article class="metric-card"><div class="metric-top"><span class="metric-index">01</span><span class="metric-direction up">Higher is better ↑</span></div><h3>ADPR</h3><p class="metric-full-name">Asynchronous Dependency Pass Rate</p><div class="formula" aria-label="ADPR equals one divided by the number of dependencies, times the sum of final dependency states">ADPR = <span class="fraction"><span>1</span><span>|A|</span></span> Σ<sub>d∈A</sub> I<sub>d,T</sub></div><p>The fraction of benchmark-defined dependencies satisfied in the <strong>final integrated workspace</strong>. It answers: did the independently implemented components ultimately become compatible?</p></article><article class="metric-card"><div class="metric-top"><span class="metric-index">02</span><span class="metric-direction down">Lower is better ↓</span></div><h3>DRS</h3><p class="metric-full-name">Dependency Resolution Step</p><div class="formula formula-stack"><span>DRS<sub>d</sub> = min { t : I<sub>d,t</sub> = 1 }</span><span>DRŜ<sub>d</sub> = DRS<sub>d</sub> / (T + 1)</span></div><p>The first logical integration checkpoint where dependency <em>d</em> passes. If it never passes, <strong>DRS<sub>d</sub> = T + 1</strong>, so normalized DRS is <strong>1</strong>.</p></article></div><div class="metric-note"><strong>Outcome + trajectory.</strong><span>ADPR captures final dependency resolution; normalized DRS distinguishes early resolution from late or absent resolution. DRS is checkpoint-based—not wall-clock time—and is not reported for SINGLE because that protocol exposes only the final workspace.</span><a href="${PAPER_URL}" target="_blank" rel="noreferrer">Definitions in §3.3 ↗</a></div></div></section>
    ${quickStart(false)}
    <section class="section"><div class="container"><div class="section-head"><span class="section-kicker">Use & extend</span><div><h2>Built for reproducible evaluation.</h2><p class="section-lede">Run the built-in OpenHands adapter or connect your own coding agent without replacing benchmark semantics.</p></div></div><div class="closing-grid"><article class="closing-card citation-card" id="citation"><div class="citation-head"><div><span class="paper-label">arXiv:2609.32662 · cs.SE</span><h3>Cite AsynCodeBench</h3><p>AsynCodeBench: Benchmarking Collaboration of Asynchronous Multi-Agent Systems in Software Engineering</p></div><div class="paper-actions"><a class="button primary" href="${PAPER_URL}" target="_blank" rel="noreferrer">Read the paper ↗</a><a class="button" href="${PAPER_PDF}" target="_blank" rel="noreferrer">PDF ↗</a></div></div>${copyBlock(BIBTEX,"bibtex")}</article><article class="closing-card"><h3>Apache-2.0</h3><p>Benchmark code and metadata are released under Apache-2.0. Upstream projects retain their own licenses.</p><a href="${REPO_FILE("LICENSE")}">Read the license →</a></article><article class="closing-card"><h3>Contributors</h3><p>Created and maintained by Kaituo Zhang, with community contributions welcome.</p><a href="${REPO_ROOT}/graphs/contributors">Meet the contributors →</a></article></div></div></section>
  </main>${footer()}`;
}

function quickStart(linkMore=true) {
  return `<section class="section"><div class="container"><div class="quick-shell"><span class="section-kicker" style="color:var(--lime)">Three steps</span><h2>From clone to a validated dry run.</h2><p class="section-lede">Start with cachetools and one protocol. The dry run checks configuration without starting a container or spending model tokens.</p><div class="steps">
    <div class="step"><span class="step-index">01</span><h3>Install</h3>${copyBlock(`git clone https://github.com/KaituoZhang/AsynCodeBench.git AsynCodeBench\ncd AsynCodeBench\nbash scripts/setup_evaluation.sh`)}</div>
    <div class="step"><span class="step-index">02</span><h3>Configure</h3>${copyBlock(`cd reproductions/async-swe-agents\ncp .env.example .env\n# Add LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL`)}</div>
    <div class="step"><span class="step-index">03</span><h3>Dry run</h3>${copyBlock(`export ENV_FILE="$PWD/.env"\nsource scripts/env.sh\nuv run asyncodebench run \\\n  --task asyncodebench:cachetools \\\n  --protocol async_private \\\n  --model "$LLM_MODEL" \\\n  --dry-run`)}</div>
  </div>${linkMore?'<div class="hero-actions"><a class="button" href="/run/">Open the complete run guide →</a></div>':''}</div></div></section>`;
}

function tasksPage() {
  document.title = "Tasks — AsynCodeBench";
  document.body.innerHTML = `${header("tasks")}<main id="main"><section class="page-hero"><div class="container"><div class="breadcrumbs"><a href="/">Overview</a> / Tasks</div><span class="eyebrow">Official task set</span><h1>Choose where your agents collaborate.</h1><p class="hero-copy">Every task exposes real cross-file dependencies, fixed ownership, executable checks, and the same five controlled protocols.</p><div class="category-summary">${CATEGORIES.map(c=>`<button class="category-stat" type="button" data-category="${c.name}"><strong>${c.count}</strong><span>${c.name}</span><small>${c.percentage}</small></button>`).join("")}</div><div class="toolbar"><input class="search" id="task-search" type="search" placeholder="Search tasks or categories…" aria-label="Search tasks"><select id="domain-filter" aria-label="Filter by category"><option value="">All categories</option>${CATEGORIES.map(c=>`<option>${c.name}</option>`).join("")}</select><span id="task-count" class="pill">${TASKS.length} tasks</span></div><div class="task-grid" id="task-grid"></div></div></section></main>${footer()}`;
  const render = () => {
    const q = document.querySelector("#task-search").value.toLowerCase().trim();
    const category = document.querySelector("#domain-filter").value;
    const filtered = TASKS.filter(t => (!category || t.category===category) && (!q || `${t.id} ${t.project} ${t.category} ${t.domain} ${t.summary}`.toLowerCase().includes(q)));
    document.querySelector("#task-count").textContent = `${filtered.length} task${filtered.length===1?"":"s"}`;
    document.querySelector("#task-grid").innerHTML = filtered.length ? filtered.map(taskCard).join("") : '<div class="empty">No tasks match this search.</div>';
  };
  document.querySelector("#task-search").addEventListener("input", render);
  document.querySelector("#domain-filter").addEventListener("change", render);
  document.querySelectorAll("[data-category]").forEach(button => button.addEventListener("click", () => {
    const select = document.querySelector("#domain-filter");
    select.value = select.value === button.dataset.category ? "" : button.dataset.category;
    document.querySelectorAll("[data-category]").forEach(item => item.classList.toggle("active", item.dataset.category === select.value));
    render();
  }));
  render();
}

const taskCard = t => `<a class="task-card" href="/tasks/task.html?id=${t.id}"><div class="task-card-top"><span class="repo-tag">${t.category}</span><span class="task-arrow">↗</span></div><h2>${t.id}</h2><p>${t.summary}</p><div class="task-meta"><span>${t.domain}</span><span>${t.agents} specialists</span><span>${t.deps} dependencies</span></div></a>`;

async function taskPage(id) {
  const task = TASKS.find(t=>t.id===id);
  if (!task) return notFound();
  document.title = `${task.id} — AsynCodeBench task`;
  document.body.innerHTML = `${header("tasks")}<main id="main"><section class="page-hero"><div class="container"><div class="breadcrumbs"><a href="/">Overview</a> / <a href="/tasks/">Tasks</a> / ${task.id}</div><span class="eyebrow">${task.category} · ${task.project}</span><h1>${task.id}</h1><p class="hero-copy">${task.summary}</p></div></section><div class="container task-layout"><article class="task-main">
    <section class="content-block"><h2>What agents must coordinate</h2><p>This task is split into natural, repository-level subproblems. Agents own specific files or integration surfaces, while executable Dependency Checkers verify the assumptions that cross those boundaries.</p><div class="team-list" id="team-list"><div class="team-member">Loading task annotations…</div></div></section>
    <section class="content-block"><h2>Dependency map</h2><p>The arrows are the benchmark—not decoration. Each one is a labeled contract checked on producer, consumer, and integrated repository states.</p><div class="legend"><span><i style="background:#2563eb"></i>IF · interface</span><span><i style="background:#7c3aed"></i>API · public API</span><span><i style="background:#d97706"></i>STATE · shared state</span><span><i style="background:#059669"></i>INT · integration</span></div><div class="graph-frame"><img src="/assets/tasks/${task.id}.svg" alt="${task.id} dependency graph and contract descriptions"></div></section>
    <section class="content-block"><h2>Run this task</h2><p>Choose a protocol for a focused run, or select all five for the complete controlled comparison.</p>${runner(task.id)}</section>
  </article><aside class="task-side"><div class="side-card"><h3>Task facts</h3><div class="facts"><div class="fact"><span>Project</span><strong>${task.project}</strong></div><div class="fact"><span>Specialists</span><strong>${task.agents}</strong></div><div class="fact"><span>Dependency points</span><strong>${task.deps}</strong></div><div class="fact"><span>Protocols</span><strong>5</strong></div><div class="fact"><span>Environment</span><strong>Docker · amd64</strong></div></div><a class="button primary" href="#task-runner">Generate command</a></div></aside></div></main>${footer()}`;
  await hydrateTaskSvg(task.id);
  wireRunner(task.id);
}

function runner(taskId) {
  return `<div class="runner" id="task-runner"><div class="runner-controls"><label>Protocol<select id="protocol-select">${PROTOCOLS.map(p=>`<option value="${p[0]}" ${p[0]==="async_private"?"selected":""}>${p[1]}</option>`).join("")}<option value="all">All five protocols</option></select></label><label>Mode<select id="mode-select"><option value="dry">Dry run · no model spend</option><option value="real">Full evaluation</option></select></label></div><div id="runner-code"></div></div>`;
}

function buildRunnerCommand(taskId, protocol, dry) {
  const compilerTask = taskId.startsWith("apache-tvm-");
  if (protocol === "all") {
    const wrapper = compilerTask ? "scripts/run_pr_hard_five_protocols_env.sh" : "scripts/run_asyncodebench_five_protocols_env.sh";
    return `ENV_FILE="$PWD/.env" \\\n+MODEL_TAG=my-model \\\n+RUN_VERSION=${dry ? "smoke-v01" : "official-v01"} \\\n+${dry ? "DRY_RUN=1" : "WORKSPACE_PORT_STRATEGY=auto"} \\\n+${wrapper} ${taskId}`;
  }
  if (protocol === "async_manager" && dry) {
    return `./.venv/bin/python run_async_manager.py \\\n+  --task_id=asyncodebench:${taskId} \\\n+  --model="$LLM_MODEL" \\\n+  --model_tag=my-model \\\n+  --run_id=dry \\\n+  --dry_run`;
  }
  if (protocol === "async_manager") {
    const wrapperTask = compilerTask ? `pr-hard:${taskId}` : taskId;
    return `export ENV_FILE="$PWD/.env"\nexport MODEL_TAG=my-model\nexport RUN_ID=async-manager-v2-s1\nbash scripts/run_async_manager_env.sh ${wrapperTask}`;
  }
  return `uv run asyncodebench run \\\n+  --task asyncodebench:${taskId} \\\n+  --protocol ${protocol} \\\n+  --model "$LLM_MODEL"${dry ? " \\\n+  --dry-run" : ""}`;
}

function wireRunner(taskId) {
  const update = () => {
    const protocol = document.querySelector("#protocol-select").value;
    const dry = document.querySelector("#mode-select").value === "dry";
    const command = `uv run asyncodebench run \\\n+  --task asyncodebench:${taskId} \\\n+  --protocol ${protocol} \\\n+  --model "$LLM_MODEL"${dry ? " \\\n+  --dry-run" : ""}`;
    document.querySelector("#runner-code").innerHTML = copyBlock(buildRunnerCommand(taskId, protocol, dry));
    wireCopies(document.querySelector("#runner-code"));
  };
  document.querySelector("#protocol-select").addEventListener("change", update);
  document.querySelector("#mode-select").addEventListener("change", update);
  update();
}

async function hydrateTaskSvg(id) {
  try {
    const text = await fetch(`/assets/tasks/${id}.svg`).then(r=>r.text());
    const doc = new DOMParser().parseFromString(text, "image/svg+xml");
    const nodes = [...doc.querySelectorAll(".graph-node")].map(rect => {
      const nodeId = rect.getAttribute("data-node");
      const x = Number(rect.getAttribute("x"));
      const y = Number(rect.getAttribute("y"));
      const texts = [...doc.querySelectorAll("text")].filter(t => Math.abs(Number(t.getAttribute("x"))- (x+18)) < 2 && Number(t.getAttribute("y")) >= y && Number(t.getAttribute("y")) <= y+140).map(t=>t.textContent.trim());
      return { id:nodeId, title:texts[0] || nodeId.replaceAll("_"," "), file:texts.find(v=>v.includes("/") || v.endsWith(".py") || v.endsWith(".cc")) || "integration surface", owner:(texts.find(v=>v.startsWith("owner:")) || "owner: integrator").replace("owner:","").trim() };
    });
    document.querySelector("#team-list").innerHTML = nodes.map(n=>`<div class="team-member"><strong>${n.title}</strong><span>${n.owner}</span><br><code>${n.file}</code></div>`).join("");
  } catch (_) {
    document.querySelector("#team-list").innerHTML = '<div class="team-member">See the dependency map below for the frozen ownership annotations.</div>';
  }
}

function advancedRunSections() {
  return `<section class="run-section" id="five-protocols"><span class="section-kicker">Complete comparison</span><h2>Run all five protocols</h2><p>This wrapper includes the frozen four conditions plus the registry-defined writable Async-Manager condition. Use the dry run first, then start the complete evaluation.</p><h3>Dry run all five</h3>${copyBlock(buildRunnerCommand("cachetools", "all", true))}<h3>Run all five</h3>${copyBlock(buildRunnerCommand("cachetools", "all", false))}</section>
  <section class="run-section" id="async-manager"><span class="section-kicker">New protocol</span><h2>Run Async-Manager directly</h2><p>Unlike Async-Read Only-Manager, the persistent Async-Manager observes every integration checkpoint and may submit harness-validated, scope-constrained production patches.</p><h3>Dry run</h3>${copyBlock(buildRunnerCommand("cachetools", "async_manager", true))}<h3>Full evaluation</h3>${copyBlock(buildRunnerCommand("cachetools", "async_manager", false))}</section>`;
}

function runPage() {
  document.title = "Quick Run — AsynCodeBench";
  document.body.innerHTML = `${header("run")}<main id="main"><section class="page-hero"><div class="container"><div class="breadcrumbs"><a href="/">Overview</a> / Quick Run</div><span class="eyebrow">Start here</span><h1>Run one task in minutes.</h1><p class="hero-copy">The benchmark image, task contract, ownership, dependency checks, and evaluator are selected for you. Bring Docker and an OpenAI-compatible model endpoint.</p></div></section><div class="container run-layout"><nav class="run-nav" aria-label="On this page"><a href="#requirements">Requirements</a><a href="#install">1. Install</a><a href="#configure">2. Configure</a><a href="#verify">3. Verify</a><a href="#run">4. Run</a><a href="#five-protocols">All five</a><a href="#async-manager">Async-Manager</a><a href="#own-agent">Bring your agent</a></nav><article class="run-content">
    <section class="run-section" id="requirements"><h2>Requirements</h2><ul class="checks"><li>Linux x86_64 host</li><li>Python 3.12 and uv</li><li>Docker available without sudo</li><li>Git and enough disk space for task images</li><li>An OpenAI-compatible endpoint or local vLLM server</li></ul><div class="callout">Want the fastest confidence check? Use <strong>doctor --offline</strong>, then dry-run cachetools. A dry run does not call the model or start a task container.</div></section>
    <section class="run-section" id="install"><span class="section-kicker">Step 1</span><h2>Install the harness</h2><p>Clone the official <code>main</code> branch and run the setup contract.</p>${copyBlock(`git clone https://github.com/KaituoZhang/AsynCodeBench.git AsynCodeBench\ncd AsynCodeBench\nbash scripts/setup_evaluation.sh`)}<h3>Faster setup, skip the test suite</h3>${copyBlock(`ASYNCODEBENCH_SETUP_SKIP_TESTS=1 bash scripts/setup_evaluation.sh`)}</section>
    <section class="run-section" id="configure"><span class="section-kicker">Step 2</span><h2>Connect your model</h2>${copyBlock(`cd reproductions/async-swe-agents\ncp .env.example .env`)}<p>Add the endpoint and model values to <code>.env</code>:</p>${copyBlock(`LLM_BASE_URL=https://your-endpoint.example/v1\nLLM_API_KEY=your-api-key\nLLM_MODEL=openai/your-model-name\nLLM_SUBAGENT_MODEL=\nSDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk`,"dotenv")}</section>
    <section class="run-section" id="verify"><span class="section-kicker">Step 3</span><h2>Verify before spending tokens</h2>${copyBlock(`export ENV_FILE="$PWD/.env"\nsource scripts/env.sh\nuv run asyncodebench doctor --offline\nuv run asyncodebench release-status --require preview\nuv run asyncodebench tasks\nuv run asyncodebench images list`)}<h3>Dry-run one task</h3>${copyBlock(`uv run asyncodebench run \\\n+  --task asyncodebench:cachetools \\\n+  --protocol async_private \\\n+  --model "$LLM_MODEL" \\\n+  --dry-run`)}</section>
    <section class="run-section" id="run"><span class="section-kicker">Step 4</span><h2>Start the evaluation</h2><p>Remove <code>--dry-run</code> when the plan looks correct. Missing task images are pulled automatically by immutable digest.</p>${copyBlock(`uv run asyncodebench run \\\n+  --task asyncodebench:cachetools \\\n+  --protocol async_private \\\n+  --model "$LLM_MODEL"`)}<p><a class="button" href="/tasks/">Choose another task →</a></p></section>
    <section class="run-section" id="own-agent"><h2>Bring your own agent</h2><p>A third-party adapter receives only the active assignment, workspace, writable paths, targeted tests, dependency labels, and budget. The harness still controls evaluation.</p>${copyBlock(`uv run asyncodebench run \\\n+  --task asyncodebench:cachetools \\\n+  --protocol all \\\n+  --model "$LLM_MODEL" \\\n+  --agent-import-path my_agents.cache_agent:CacheAgent \\\n+  --run-id custom-agent-v01`)}<p><a href="${REPO}/blob/docs/AGENT_ADAPTER.md">Read the adapter guide →</a></p></section>
    ${advancedRunSections()}
  </article></div></main>${footer()}`;
}

function notFound(){ document.title="Not found — AsynCodeBench"; document.body.innerHTML=`${header("")}<main id="main"><section class="page-hero"><div class="container"><span class="eyebrow">404</span><h1>This page is not part of the benchmark.</h1><a class="button primary" href="/tasks/">Browse official tasks</a></div></section></main>${footer()}`; }

function wireCopies(scope=document) {
  scope.querySelectorAll("[data-copy]").forEach(button => button.addEventListener("click", async () => {
    const text = button.previousElementSibling.innerText;
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
    setTimeout(()=>button.textContent="Copy", 1400);
  }));
}

function fixRepositoryLinks() {
  document.querySelectorAll("a[href]").forEach(link => {
    link.href = link.href
      .replace("/tree/main/blob/", "/blob/main/")
      .replace("/tree/main/graphs/", "/graphs/");
  });
}

const page = document.documentElement.dataset.page;
if (page === "home") home();
else if (page === "tasks") tasksPage();
else if (page === "run") runPage();
else if (page === "task") taskPage(document.documentElement.dataset.task || new URLSearchParams(location.search).get("id"));
else notFound();
fixRepositoryLinks();
wireCopies();
