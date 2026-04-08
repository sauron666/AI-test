/* ══════════════════════════════════════════════════
   SAURON dashboard — zero-build SPA controller
   ══════════════════════════════════════════════════ */
(() => {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // ── tab switching ─────────────────────────────
  $$(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".tab").forEach((t) => t.classList.remove("active"));
      btn.classList.add("active");
      const view = btn.dataset.view;
      $$(".view").forEach((v) => v.classList.remove("active"));
      $("#view-" + view)?.classList.add("active");
      if (view === "engagements") loadEngagements();
      if (view === "tools")       loadTools();
      if (view === "findings")    loadFindings();
      if (view === "reports")     loadReports();
      if (view === "settings")    loadSettings();
    });
  });

  // ── boot ───────────────────────────────────────
  async function boot() {
    WS.connect();
    WS.subscribe(onAgentEvent);

    // Auto-login with default creds for the demo / hackathon boot
    try {
      if (!API.token()) {
        const r = await API.login("operator", "change-me").catch(() => null);
        if (r && r.access_token) API.setToken(r.access_token);
      }
    } catch (e) { console.warn("auto-login failed", e); }

    try {
      const tools = await API.listTools();
      $("#m-tools").textContent = tools.length;
    } catch {}

    try {
      const engs = await API.listEngagements();
      $("#m-engagements").textContent = engs.length;
    } catch {}

    try {
      const providers = await API.llmProviders();
      $("#system-prompt-preview").textContent = "Available providers: " +
        (providers.available || []).join(", ");
    } catch {}
  }

  // ── activity feed / ws events ─────────────────
  function ts() { return new Date().toLocaleTimeString(); }
  function feedLine(kind, content) {
    const feed = $("#activity-feed");
    const d = document.createElement("div");
    d.className = "entry " + kind;
    d.innerHTML = `<span class="ts">${ts()}</span>${escape(content)}`;
    feed.prepend(d);
    while (feed.children.length > 200) feed.lastElementChild.remove();
  }
  function termLine(cls, content) {
    const body = $("#terminal-body");
    const d = document.createElement("div");
    d.className = "t-line " + cls;
    d.textContent = content;
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }
  const escape = (s) => String(s).replace(/[&<>]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

  function onAgentEvent(evt) {
    switch (evt.type) {
      case "hello":
        termLine("t-meta", "◉ " + evt.message);
        break;
      case "engagement.start":
        feedLine("phase", `ENGAGEMENT START — phases: ${(evt.phases||[]).join(" → ")}`);
        break;
      case "phase.start":
        feedLine("phase", `▶ phase: ${evt.phase}`);
        $$(".phase").forEach((p) => p.classList.remove("active"));
        $(`.phase[data-phase="${evt.phase}"]`)?.classList.add("active");
        break;
      case "phase.complete":
        feedLine("phase", `✓ phase complete: ${evt.phase}`);
        $(`.phase[data-phase="${evt.phase}"]`)?.classList.add("done");
        break;
      case "agent.thought":
        feedLine("thought", `💭 ${evt.content.slice(0, 220)}`);
        break;
      case "agent.action":
        feedLine("action", `⚔  ${evt.tool}  ${JSON.stringify(evt.arguments).slice(0, 200)}`);
        termLine("t-prompt", `sauron@${evt.phase}:~$ ${evt.tool} ${JSON.stringify(evt.arguments)}`);
        break;
      case "agent.observation":
        feedLine("observation", `📥 ${evt.tool} → exit=${evt.result?.exit_code ?? "?"}`);
        const out = (evt.result && evt.result.stdout) || "";
        out.split("\n").slice(0, 20).forEach((l) => termLine("t-out", l));
        break;
      case "agent.reflection":
        feedLine("reflection", `🔍 ${evt.content.slice(0, 220)}`);
        break;
      case "agent.error":
        feedLine("error", `✗ ${evt.error}`);
        break;
      case "engagement.complete":
        feedLine("phase", `★ ENGAGEMENT COMPLETE — ${evt.findings || 0} findings`);
        break;
    }
  }

  // ── engagements ───────────────────────────────
  async function loadEngagements() {
    const list = $("#engagement-list");
    list.innerHTML = "loading…";
    try {
      const engs = await API.listEngagements();
      $("#m-engagements").textContent = engs.length;
      if (!engs.length) { list.innerHTML = '<p class="hint">No engagements yet. Click "New Engagement" to launch one.</p>'; return; }
      list.innerHTML = "";
      engs.forEach((e) => {
        const row = document.createElement("div");
        row.className = "item";
        row.innerHTML = `
          <div>
            <div class="title">${escape(e.name)}</div>
            <div class="meta">${e.profile} · ${e.status} · ${new Date(e.created_at).toLocaleString()}</div>
          </div>
          <div>
            <button class="btn" data-start="${e.id}">▶ start</button>
            <button class="btn" data-report="${e.id}">📄 report</button>
          </div>`;
        list.appendChild(row);
      });
      list.onclick = async (ev) => {
        const s = ev.target.dataset.start;
        const r = ev.target.dataset.report;
        if (s) { await API.startEngagement(s); feedLine("phase", "▶ starting " + s); }
        if (r) { const res = await API.buildReport(r); alert("Report built:\n" + JSON.stringify(res, null, 2)); }
      };
    } catch (e) { list.textContent = "error: " + e.message; }
  }

  // ── tools ─────────────────────────────────────
  let _toolsCache = [];
  async function loadTools() {
    if (!_toolsCache.length) _toolsCache = await API.listTools();
    const grid = $("#tool-grid");
    const filter = $("#tool-filter").value.toLowerCase();
    const dom = $("#tool-domain-filter").value;
    grid.innerHTML = "";
    const domains = new Set(_toolsCache.map((t) => t.domain));
    const sel = $("#tool-domain-filter");
    if (sel.children.length <= 1) {
      [...domains].sort().forEach((d) => {
        const o = document.createElement("option"); o.value = d; o.textContent = d;
        sel.appendChild(o);
      });
    }
    _toolsCache
      .filter((t) => (!dom || t.domain === dom))
      .filter((t) => !filter || (t.name + t.desc + t.cmd).toLowerCase().includes(filter))
      .forEach((t) => {
        const card = document.createElement("div");
        card.className = "tool";
        card.innerHTML = `
          <div class="name">${escape(t.name)}</div>
          <div class="cmd">${escape(t.cmd)}</div>
          <div class="desc">${escape(t.desc || t.category)}</div>
          <span class="tag">${escape(t.domain)}</span>`;
        grid.appendChild(card);
      });
  }
  $("#tool-filter")?.addEventListener("input", loadTools);
  $("#tool-domain-filter")?.addEventListener("change", loadTools);

  // ── findings / reports / settings ────────────
  async function loadFindings() {
    const list = $("#findings-list");
    list.innerHTML = '<p class="hint">Select an engagement in the Engagements view to inspect findings.</p>';
  }
  async function loadReports() {
    const list = $("#reports-list");
    list.innerHTML = '<p class="hint">Reports are generated per engagement. Use the "📄 report" button in Engagements.</p>';
  }
  async function loadSettings() {
    try {
      const r = await API.llmProviders();
      const div = $("#llm-providers");
      div.innerHTML = "";
      const catalog = r.catalog?.providers || {};
      const avail = new Set(r.available || []);
      Object.entries(catalog).forEach(([k, cfg]) => {
        const wrap = document.createElement("div");
        wrap.style.marginBottom = "12px";
        wrap.innerHTML = `
          <strong style="color:${avail.has(k) ? "var(--green)" : "var(--fg-2)"}">
            ${avail.has(k) ? "✓" : "✗"} ${cfg.display_name}
          </strong>
          <div class="hint">default: ${cfg.default_model}</div>`;
        div.appendChild(wrap);
      });
    } catch (e) { $("#llm-providers").textContent = e.message; }
  }

  // ── new engagement modal ──────────────────────
  async function openModal() {
    const profiles = await API.profiles();
    const llms = (await API.llmProviders()).available || [];
    const psel = $("#f-profile"); psel.innerHTML = "";
    profiles.forEach((p) => {
      const o = document.createElement("option");
      o.value = p.key; o.textContent = p.display_name;
      psel.appendChild(o);
    });
    const lsel = $("#f-llm"); lsel.innerHTML = "";
    llms.forEach((l) => {
      const o = document.createElement("option");
      o.value = l; o.textContent = l;
      lsel.appendChild(o);
    });
    $("#modal").classList.remove("hidden");
  }
  $("#new-engagement")?.addEventListener("click", openModal);
  $("#modal-cancel")?.addEventListener("click", () => $("#modal").classList.add("hidden"));
  $("#modal-submit")?.addEventListener("click", async () => {
    let scope = {};
    try { scope = JSON.parse($("#f-scope").value); } catch {}
    const payload = {
      name: $("#f-name").value || "untitled-" + Date.now(),
      profile: $("#f-profile").value,
      scope,
      rules_of_engagement: $("#f-roe").value,
      stealth_profile: $("#f-stealth").value,
      llm_provider: $("#f-llm").value || null,
    };
    try {
      await API.createEngagement(payload);
      $("#modal").classList.add("hidden");
      loadEngagements();
    } catch (e) { alert(e.message); }
  });

  boot();
})();
