let allocChart = null;

function fmtIls(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IL", { maximumFractionDigits: 0 }) + " ₪";
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const v = Number(n);
  const cls = v >= 0 ? "positive" : "negative";
  return `<span class="${cls}">${v.toFixed(3)}%</span>`;
}

function fmtBytes(n) {
  if (n == null || Number.isNaN(n) || n < 0) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let x = Number(n);
  while (x >= 1024 && i < u.length - 1) {
    x /= 1024;
    i++;
  }
  return `${x.toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
}

function daysParam() {
  return document.getElementById("days").value;
}

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setStatus(msg, err = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.style.color = err ? "#f66d6d" : "";
}

function setSvStatus(msg, err = false) {
  const el = document.getElementById("sv-status");
  if (!el) return;
  el.textContent = msg;
  el.style.color = err ? "#f66d6d" : "";
}

function activeTabId() {
  const t = document.querySelector("nav.tabs .tab.active");
  return t ? t.dataset.tab : "portfolio";
}

function renderPortfolio(p) {
  const sess = p.session || {};
  const cards = document.getElementById("summary-cards");
  const ret = p.portfolio_return_pct != null ? fmtPct(p.portfolio_return_pct) : "—";
  const alpha = p.alpha_pct != null ? fmtPct(p.alpha_pct) : "—";
  cards.innerHTML = `
    <div class="card"><div class="label">NAV</div><div class="value">${fmtIls(p.nav_ils)}</div><div class="sub">session start ${fmtIls(sess.initial_nav_ils)}</div></div>
    <div class="card"><div class="label">Return vs session</div><div class="value">${ret}</div><div class="sub">α vs TA-35 ${alpha}</div></div>
    <div class="card"><div class="label">Cash</div><div class="value">${fmtIls(p.cash_ils)}</div><div class="sub">${p.cash_pct}% of NAV</div></div>
    <div class="card"><div class="label">Benchmark</div><div class="value">${sess.benchmark_symbol || "TA35.TA"}</div><div class="sub">TA-35 ${fmtPct(p.benchmark_return_pct)} · start ${sess.benchmark_start_px ?? "—"}</div></div>
  `;

  const tbody = document.querySelector("#positions-table tbody");
  tbody.innerHTML = (p.positions || [])
    .map(
      (row) =>
        `<tr><td>${escapeHtml(row.symbol)}</td><td>${escapeHtml(String(row.qty))}</td><td>${row.last_price ?? "—"}</td><td>${fmtIls(row.market_value_ils)}</td></tr>`
    )
    .join("");

  const labels = (p.allocation || []).map((a) => a.label);
  const values = (p.allocation || []).map((a) => a.value_ils);
  const ctx = document.getElementById("alloc-chart");
  if (allocChart) allocChart.destroy();
  allocChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ["#3d8bfd", "#3dd68c", "#f0b429", "#b388ff", "#ff7eb9", "#6ee7b7"] }],
    },
    options: { plugins: { legend: { position: "bottom", labels: { color: "#8b9cb3" } } } },
  });
}

function renderCycles(data) {
  const root = document.getElementById("cycles-list");
  const cycles = data.cycles || [];
  if (!cycles.length) {
    root.innerHTML = "<p class='muted'>No cycles in this timeframe.</p>";
    return;
  }
  root.innerHTML = cycles
    .map((c) => {
      const openCls = c.market_open ? "open" : "closed";
      const openLbl = c.market_open ? "Market open" : "Market closed";
      const perf = `Portfolio ${fmtPct(c.portfolio_return_pct)} · TA-35 ${fmtPct(c.benchmark_return_pct)} · α ${fmtPct(c.alpha_pct)}`;
      const actions = (c.actions || [])
        .map((a) => {
          if (a.type === "trade") {
            const side = (a.side || "").toLowerCase();
            return `<div class="action"><span class="side-${side}">${escapeHtml(a.side)} ${escapeHtml(a.symbol)} ×${escapeHtml(String(a.qty))}</span> — ${escapeHtml(a.reason_he || "")}</div>`;
          }
          if (a.type === "blocked") {
            return `<div class="action">⏸ Blocked ${escapeHtml(a.side || "")} ${escapeHtml(a.symbol || "")} — ${escapeHtml(a.reason_he || "after hours")}</div>`;
          }
          if (a.type === "hold") {
            return `<div class="action">Hold — ${escapeHtml(a.reason_he || "")}</div>`;
          }
          return `<div class="action">${escapeHtml(a.type)} ${escapeHtml(a.symbol || "")} — ${escapeHtml(a.reason_he || "")}</div>`;
        })
        .join("");
      const summary = c.summary_he ? `<p class="muted">${escapeHtml(c.summary_he)}</p>` : "";
      return `
        <article class="cycle">
          <div class="cycle-head">
            <span class="ts">#${c.cycle_id} · ${escapeHtml(c.ts)}</span>
            <span class="badge ${openCls}">${openLbl}</span>
            <span class="badge">${c.executed_trades} executed</span>
            <span class="muted">${perf}</span>
          </div>
          ${summary}
          ${actions || "<p class='muted'>No trades this cycle.</p>"}
        </article>`;
    })
    .join("");
}

function renderKnowledge(data) {
  const root = document.getElementById("knowledge-list");
  const items = data.items || [];
  if (!items.length) {
    root.innerHTML = "<p class='muted'>No knowledge events in this timeframe.</p>";
    return;
  }
  root.innerHTML = items
    .map((k) => {
      const title = k.title_en || k.title;
      const sum = k.executive_summary_en || "(no summary yet)";
      const flash = k.is_maya_flash ? '<span class="badge open">Maya flash</span>' : "";
      return `
        <article class="k-item">
          <h3>${escapeHtml(title)}</h3>
          <div class="k-meta">${escapeHtml(k.event_time || k.ts)} · ${escapeHtml(k.source)} · ${escapeHtml(k.matched_symbol || "—")}
            · ${escapeHtml(k.sentiment || "—")} · ${escapeHtml(k.trade_usefulness || "—")} ${flash}</div>
          <p class="k-summary">${escapeHtml(sum)}</p>
          ${k.url ? `<p class="muted"><a href="${escapeHtml(k.url)}" target="_blank" rel="noopener">source</a></p>` : ""}
        </article>`;
    })
    .join("");
}

function formatPromptSectionBody(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    const meta = [];
    if (v.chars != null) meta.push(`${v.chars} chars`);
    if (v.lines != null) meta.push(`${v.lines} lines`);
    const prev = v.preview != null ? String(v.preview) : "";
    const full = v.full != null ? String(v.full) : "";
    const head = meta.length ? `# ${meta.join(", ")}\n\n` : "";
    if (full && full !== prev) return `${head}${prev}\n\n— full —\n\n${full}`;
    return head + prev;
  }
  return JSON.stringify(v, null, 2);
}

function renderSupervisionOverview(ov) {
  const paths = ov.paths || {};
  const db = paths.db || {};
  const st = paths.state || {};
  const cards = `
    <section class="cards" style="margin-bottom:1rem">
      <div class="card"><div class="label">SQLite DB</div><div class="value" style="font-size:0.95rem">${escapeHtml(paths.db_path || "")}</div>
        <div class="sub">${db.exists ? fmtBytes(db.bytes) + " · " + escapeHtml(db.modified || "") : "missing"}</div></div>
      <div class="card"><div class="label">Paper state JSON</div><div class="value" style="font-size:0.95rem">${escapeHtml(paths.state_path || "")}</div>
        <div class="sub">${st.exists ? fmtBytes(st.bytes) + " · " + escapeHtml(st.modified || "") : "missing"}</div></div>
      <div class="card"><div class="label">Cycle log directory</div><div class="value" style="font-size:0.95rem">${escapeHtml(paths.cycle_log_dir || "")}</div>
        <div class="sub">${paths.cycle_log_dir_exists ? `${paths.cycle_log_file_count} files · listed ${fmtBytes(paths.cycle_log_listed_bytes_sum)}` : "missing"}</div></div>
    </section>`;

  const tblRows = (ov.sqlite_tables || [])
    .map(
      (r) =>
        `<tr><td><code>${escapeHtml(r.name)}</code></td><td>${r.rows}</td><td class="muted">${escapeHtml(r.purpose || "")}</td></tr>`
    )
    .join("");
  const table = `
    <section>
      <h2>SQLite tables</h2>
      <div class="sv-scroll">
        <table class="sv-table"><thead><tr><th>Table</th><th>Rows</th><th>Role</th></tr></thead>
        <tbody>${tblRows || "<tr><td colspan='3' class='muted'>No database</td></tr>"}</tbody></table>
      </div>
    </section>`;

  const flow = (ov.data_flow || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("");
  const mr = ov.model_runtime || {};
  const mrDl = Object.keys(mr)
    .map((k) => `<dt>${escapeHtml(k)}</dt><dd><code>${escapeHtml(JSON.stringify(mr[k]))}</code></dd>`)
    .join("");

  document.getElementById("sv-overview").innerHTML = `
    ${cards}
    ${table}
    <section style="margin-top:1rem">
      <h2>What each cycle touches</h2>
      <ul class="muted">${flow}</ul>
      <h3>Model / runtime (from current process env)</h3>
      <p class="muted">Values reflect the dashboard server’s <code>Config()</code>, not necessarily the host that last ran <code>demo_trader</code>.</p>
      <dl class="sv-dl">${mrDl}</dl>
    </section>`;
}

function fillCycleSelect(logs) {
  const sel = document.getElementById("sv-cycle-select");
  const cur = sel.value;
  sel.innerHTML = '<option value="">— pick cycle —</option>';
  for (const row of logs || []) {
    if (!row.cycle_id) continue;
    const o = document.createElement("option");
    o.value = String(row.cycle_id);
    o.textContent = `#${row.cycle_id} · ${row.filename} (${fmtBytes(row.bytes)})`;
    sel.appendChild(o);
  }
  if (logs.some((r) => String(r.cycle_id) === cur)) sel.value = cur;
}

function renderLogTable(logs) {
  const rows = (logs || [])
    .map((r) => {
      const id = r.cycle_id || 0;
      return `<tr>
        <td><code>${id}</code></td>
        <td class="muted" style="font-size:0.8rem">${escapeHtml(r.filename || "")}</td>
        <td>${fmtBytes(r.bytes)}</td>
        <td class="muted" style="font-size:0.78rem">${escapeHtml(r.modified || "")}</td>
        <td><button type="button" class="sv-linkish" data-cycle="${id}">Inspect</button></td>
      </tr>`;
    })
    .join("");
  document.getElementById("sv-log-table").innerHTML = `
    <div class="sv-scroll">
      <table class="sv-table"><thead><tr><th>Id</th><th>File</th><th>Size</th><th>Modified</th><th></th></tr></thead>
      <tbody>${rows || "<tr><td colspan='5' class='muted'>No cycle JSON files found.</td></tr>"}</tbody></table>
    </div>`;
}

function renderCycleInspect(data) {
  const root = document.getElementById("sv-inspect");
  const log = data.cycle_log;
  const decisions = data.decisions || [];
  const strip = data.strip_full_prompts;

  const decRows = decisions
    .map((d) => {
      const mj =
        d.model_json != null
          ? `<details><summary>model_json</summary><pre class="sv-pre">${escapeHtml(JSON.stringify(d.model_json, null, 2))}</pre></details>`
          : "";
      return `<tr>
        <td><code>${escapeHtml(d.kind)}</code></td>
        <td>${escapeHtml(d.symbol || "—")}</td>
        <td>${escapeHtml(d.side || "—")}</td>
        <td>${d.executed ? "yes" : "no"}</td>
        <td style="max-width:14rem;font-size:0.8rem">${escapeHtml((d.reason_he || "").slice(0, 280))}</td>
        <td>${mj}</td>
      </tr>`;
    })
    .join("");

  let logBlock = "";
  if (!log) {
    logBlock = `<p class="muted">No JSON cycle log on disk for cycle <strong>#${data.cycle_id}</strong> (logging disabled, different log directory, or file not written yet).</p>`;
  } else {
    const prompt = log.prompt || {};
    const sections = (prompt.sections && typeof prompt.sections === "object" ? prompt.sections : {}) || {};
    const secHtml = Object.keys(sections)
      .map((name) => {
        const body = formatPromptSectionBody(sections[name]);
        return `<details><summary><code>${escapeHtml(name)}</code></summary><pre class="sv-pre">${escapeHtml(body)}</pre></details>`;
      })
      .join("");

    logBlock = `
      <p><span class="sv-pill">log file</span><code>${escapeHtml(log._log_filename || "")}</code></p>
      <p><span class="sv-pill">strip full prompts</span>${strip ? "yes (API removed full text fields if present)" : "no"}</p>
      <h3>Ingest snapshot</h3>
      <pre class="sv-pre">${escapeHtml(JSON.stringify(log.ingest || {}, null, 2))}</pre>
      <h3>Model response (parsed JSON from Ollama)</h3>
      <pre class="sv-pre">${escapeHtml(JSON.stringify(log.model_response ?? log.model_error ?? {}, null, 2))}</pre>
      ${
        log.model_error
          ? `<h3>Error</h3><pre class="sv-pre" style="border:1px solid #633">${escapeHtml(String(log.model_error))}</pre>`
          : ""
      }
      <h3>Executions audit (pending list)</h3>
      <pre class="sv-pre">${escapeHtml(JSON.stringify(log.executions || [], null, 2))}</pre>
      <h3>Performance / portfolio snapshots</h3>
      <pre class="sv-pre">${escapeHtml(
        JSON.stringify(
          {
            performance_before: log.performance_before,
            performance_after: log.performance_after,
            portfolio_after: log.portfolio_after,
          },
          null,
          2
        )
      )}</pre>
      <h3>Prompt sections</h3>
      <p class="muted">Main trader call uses <code>system</code> + <code>user</code> (Hebrew block). Other keys are copies logged for supervision.</p>
      ${secHtml || "<p class='muted'>No prompt sections in file.</p>"}
    `;
  }

  root.innerHTML = `
    <h3>SQLite <code>decisions</code> for this cycle</h3>
    <div class="sv-scroll">
      <table class="sv-table"><thead><tr><th>kind</th><th>symbol</th><th>side</th><th>exec</th><th>reason (trim)</th><th>json</th></tr></thead>
      <tbody>${decRows || "<tr><td colspan='6' class='muted'>No rows (cycle id not in DB yet).</td></tr>"}</tbody></table>
    </div>
    ${logBlock}
  `;
}

async function runCycleInspect() {
  const sel = document.getElementById("sv-cycle-select");
  const id = parseInt(sel.value, 10);
  if (!id) {
    setSvStatus("Pick a cycle id first.", true);
    return;
  }
  const strip = document.getElementById("sv-strip-full").checked;
  setSvStatus("Loading cycle inspect…");
  try {
    const q = `cycle_id=${id}&strip_full_prompts=${strip ? "1" : "0"}`;
    const data = await fetchJson(`/api/supervision/cycle-inspect?${q}`);
    renderCycleInspect(data);
    setSvStatus(`Loaded inspect for #${id}`);
  } catch (e) {
    setSvStatus(String(e), true);
  }
}

async function loadSupervisionPage() {
  setSvStatus("Loading overview…");
  try {
    const ov = await fetchJson("/api/supervision/overview?cycle_log_limit=100");
    renderSupervisionOverview(ov);
    renderLogTable(ov.cycle_logs);
    fillCycleSelect(ov.cycle_logs);
    setSvStatus(`Overview loaded (${new Date().toLocaleTimeString()})`);
  } catch (e) {
    setSvStatus(String(e), true);
  }
}

async function refresh() {
  setStatus("Loading…");
  const days = daysParam();
  try {
    const [health, portfolio, cycles, knowledge] = await Promise.all([
      fetchJson("/api/health"),
      fetchJson("/api/portfolio"),
      fetchJson(`/api/cycles?days=${days}`),
      fetchJson(`/api/knowledge?days=${days}${document.getElementById("maya-only").checked ? "&maya_only=1" : ""}`),
    ]);
    if (!health.ok) setStatus("Missing data/trader.db or paper_state.json", true);
    else setStatus(`Updated ${new Date().toLocaleTimeString()}`);
    renderPortfolio(portfolio);
    renderCycles(cycles);
    renderKnowledge(knowledge);
    if (activeTabId() === "supervision") await loadSupervisionPage();
  } catch (e) {
    setStatus(String(e), true);
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "supervision") loadSupervisionPage();
  });
});

document.getElementById("refresh").addEventListener("click", refresh);
document.getElementById("days").addEventListener("change", refresh);
document.getElementById("maya-only").addEventListener("change", refresh);

const svReload = document.getElementById("sv-reload");
if (svReload) svReload.addEventListener("click", () => loadSupervisionPage());
const svBtn = document.getElementById("sv-inspect-btn");
if (svBtn) svBtn.addEventListener("click", () => runCycleInspect());

const svLogTable = document.getElementById("sv-log-table");
if (svLogTable) {
  svLogTable.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-cycle]");
    if (!btn) return;
    document.getElementById("sv-cycle-select").value = btn.dataset.cycle;
    runCycleInspect();
  });
}

refresh();
setInterval(refresh, 60_000);
