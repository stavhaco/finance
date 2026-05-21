const BAR_COLORS = ["#3d8bfd", "#3dd68c", "#f0b429", "#b388ff", "#ff7eb9", "#6ee7b7", "#8899aa"];
let refreshTimerId = null;

function fmtIls(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₪";
}

function fmtPct(n, withSpan) {
  const wrap = withSpan !== false;
  if (n == null || Number.isNaN(n)) return "—";
  const v = Number(n);
  const txt = `${v.toFixed(2)}%`;
  if (!wrap) return txt;
  const cls = v >= 0 ? "positive" : "negative";
  return `<span class="${cls}">${txt}</span>`;
}

function fmtNum2(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toFixed(2);
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

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function nl2brEscaped(s) {
  return escapeHtml(s).replace(/\n/g, "<br>");
}

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

function setStatus(msg, err = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.style.color = err ? "#f66d6d" : "";
}

function setSvBanner(msg, asError = false) {
  const b = document.getElementById("sv-error");
  if (!b) return;
  if (!msg) {
    b.hidden = true;
    b.textContent = "";
    return;
  }
  b.hidden = false;
  b.textContent = msg;
  b.classList.toggle("is-error", asError);
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

function restartAutoRefresh() {
  if (refreshTimerId) clearInterval(refreshTimerId);
  refreshTimerId = null;
  const box = document.getElementById("auto-refresh");
  if (!box || !box.checked) return;
  refreshTimerId = setInterval(refreshMainData, 120_000);
}

function renderAllocationBars(nav, rows) {
  const root = document.getElementById("alloc-bars");
  const n = Number(nav) || 0;
  if (!rows || !rows.length || n <= 0) {
    root.innerHTML = "<p class='muted'>No NAV data.</p>";
    return;
  }
  const lines = [];
  rows.forEach((row, idx) => {
    const lab = escapeHtml(row.label || row.symbol || "?");
    const v = Number(row.value_ils);
    const pctRaw = Math.max(0, (v / n) * 100);
    const pct = Math.min(100, pctRaw).toFixed(2);
    const col = BAR_COLORS[idx % BAR_COLORS.length];
    let extra = "";
    const up = row.uplift_pct;
    if (up != null && !Number.isNaN(Number(up)) && row.kind !== "cash") {
      extra = ` · vs avg buy ${escapeHtml(fmtPct(Number(up), false))}`;
    }
    lines.push(`
      <div class="allo-row">
        <div class="allo-meta"><span class="allo-label">${lab}</span><span class="allo-pct">${pct}% · ${fmtIls(v)}${extra}</span></div>
        <div class="allo-track"><div class="allo-fill" style="width:${pct}%;background:${col}"></div></div>
      </div>`);
  });
  root.innerHTML = lines.join("");
}

function renderPortfolio(p) {
  const sess = p.session || {};
  const cards = document.getElementById("summary-cards");
  const ret = p.portfolio_return_pct != null ? fmtPct(p.portfolio_return_pct) : "—";
  const alpha = p.alpha_pct != null ? fmtPct(p.alpha_pct) : "—";
  const benchLine = sess.benchmark_label || sess.benchmark_symbol || "TA35.TA";
  cards.innerHTML = `
    <div class="card"><div class="label">NAV</div><div class="value">${fmtIls(p.nav_ils)}</div><div class="sub">session start ${fmtIls(sess.initial_nav_ils)}</div></div>
    <div class="card"><div class="label">Return vs session</div><div class="value">${ret}</div><div class="sub">α vs TA-35 ${alpha}</div></div>
    <div class="card"><div class="label">Cash</div><div class="value">${fmtIls(p.cash_ils)}</div><div class="sub">${fmtNum2(p.cash_pct)}% of NAV</div></div>
    <div class="card"><div class="label">Benchmark</div><div class="value" style="font-size:1rem">${escapeHtml(String(benchLine))}</div><div class="sub">${fmtPct(p.benchmark_return_pct)} · start ${sess.benchmark_start_px != null && sess.benchmark_start_px !== "" ? fmtNum2(sess.benchmark_start_px) : "—"}</div></div>
  `;

  const tbody = document.querySelector("#positions-table tbody");
  tbody.innerHTML = (p.positions || [])
    .map(
      (row) =>
        `<tr><td>${escapeHtml(row.company_label || row.symbol)}</td><td><code>${escapeHtml(row.symbol)}</code></td><td>${fmtNum2(
          row.qty
        )}</td><td>${row.avg_buy_ils != null ? fmtIls(row.avg_buy_ils) : "—"}</td><td>${
          row.last_price != null ? fmtNum2(row.last_price) : "—"
        }</td><td>${fmtIls(row.market_value_ils)}</td><td>${
          row.unrealized_pnl_pct != null ? fmtPct(row.unrealized_pnl_pct) : "—"
        }</td></tr>`
    )
    .join("");

  renderAllocationBars(p.nav_ils, p.allocation || []);
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
      const benchLbl = c.benchmark_label ? ` · bench: ${escapeHtml(c.benchmark_label)}` : "";
      const nar = (c.summary_he || "").trim();
      const english = (c.english_digest || "").trim();
      const digestBlock =
        english.length === 0
          ? `<p class="muted digest-miss small">No English article digest (<code>knowledge_en</code>) stored in this cycle JSON.</p>`
          : `<details class="digest-en" open><summary>English article context (${english.length.toLocaleString()} chars)</summary><div class="narr-block narr-ltr">${nl2brEscaped(
              english
            )}</div></details>`;
      const narrBlock =
        nar.length === 0
          ? ""
          : `<details class="cycle-narr digest-he"><summary>Hebrew model summary — RTL (${nar.length.toLocaleString()} chars)</summary><div dir="rtl" class="rationale-rtl narr-block">${escapeHtml(
              nar
            )}</div></details>`;
      const actions = (c.actions || [])
        .map((a) => {
          const rl = escapeHtml((a.reason_he || "").trim());
          const rlBlock =
            rl.length === 0
              ? `<p class="muted">No rationale text stored for this row.</p>`
              : `<pre class="rationale-pre tight">${rl}</pre>`;
          const who = escapeHtml(a.company_label || a.symbol || "");
          if (a.type === "trade") {
            const side = (a.side || "").toLowerCase();
            return `<div class="action"><div><span class="side-${side}">${escapeHtml(a.side)}</span> · <strong>${who}</strong> ×${escapeHtml(
              String(a.qty ?? "")
            )}</div>${rlBlock}</div>`;
          }
          if (a.type === "blocked") {
            return `<div class="action"><div>Blocked ${escapeHtml(a.side || "")} · <strong>${who}</strong></div>${rlBlock}</div>`;
          }
          if (a.type === "hold") {
            return `<div class="action">${rlBlock}</div>`;
          }
          return `<div class="action"><div>${escapeHtml(a.type)} ${who}</div>${rlBlock}</div>`;
        })
        .join("");
      return `
        <article class="cycle">
          <div class="cycle-head">
            <span class="ts">#${c.cycle_id} · ${escapeHtml(c.ts)}</span>
            <span class="badge ${openCls}">${openLbl}</span>
            <span class="badge">${c.executed_trades} executed trades</span>
            <span class="muted">${perf}${benchLbl}</span>
          </div>
          ${digestBlock}
          ${narrBlock}
          ${actions || "<p class='muted'>Nothing recorded this cycle.</p>"}
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
      const match = k.matched_company_label || k.matched_symbol || "—";
      return `
        <article class="k-item">
          <h3>${escapeHtml(title)}</h3>
          <div class="k-meta">${escapeHtml(k.event_time || k.ts)} · ${escapeHtml(k.source)} · matched: ${escapeHtml(match)}
            · ${escapeHtml(k.sentiment || "—")} · ${escapeHtml(k.trade_usefulness || "—")} ${flash}</div>
          <p class="k-summary">${escapeHtml(sum)}</p>
          ${k.url ? `<p class="muted"><a href="${escapeHtml(k.url)}" target="_blank" rel="noopener">Open source link</a></p>` : ""}
        </article>`;
    })
    .join("");
}

function renderSupervisionOverview(ov) {
  const paths = ov.paths || {};
  const db = paths.db || {};
  const st = paths.state || {};
  const cards = `
    <section class="cards" style="margin-bottom:1rem">
      <div class="card"><div class="label">SQLite</div><div class="value mono-sm">${escapeHtml(paths.db_path || "")}</div>
        <div class="sub">${db.exists ? `${fmtBytes(db.bytes)} · ${escapeHtml(db.modified || "")}` : "missing"}</div></div>
      <div class="card"><div class="label">Paper state JSON</div><div class="value mono-sm">${escapeHtml(paths.state_path || "")}</div>
        <div class="sub">${st.exists ? `${fmtBytes(st.bytes)}` : "missing"}</div></div>
      <div class="card"><div class="label">Cycle logs folder</div><div class="value mono-sm">${escapeHtml(paths.cycle_log_dir || "")}</div>
        <div class="sub">${paths.cycle_log_dir_exists ? `${paths.cycle_log_file_count} files · ${fmtBytes(
          paths.cycle_logs_listed_byte_sum
        )} (sample sum)` : "missing"}</div></div>
    </section>`;

  const rows = (ov.sqlite_tables || [])
    .map(
      (t) =>
        `<tr><td><code>${escapeHtml(t.name)}</code></td><td>${t.rows}</td><td class="muted">${escapeHtml(t.purpose || "")}</td></tr>`
    )
    .join("");

  const notes = (ov.notes || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("");
  const mr = ov.model_runtime || {};
  const modelDl = Object.keys(mr)
    .map((k) => `<dt>${escapeHtml(k)}</dt><dd><code>${escapeHtml(JSON.stringify(mr[k]))}</code></dd>`)
    .join("");

  document.getElementById("sv-overview").innerHTML = `
    ${cards}
    <section>
      <h2>SQLite tables</h2>
      <div class="sv-scroll sv-table-wrap"><table><thead><tr><th>Name</th><th>Rows</th><th>Notes</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="3" class="muted">(no tables)</td></tr>`}</tbody></table></div>
    </section>
    <section style="margin-top:1rem">
      <h2>Operator notes</h2>
      <ul class="muted">${notes}</ul>
      <h3>Trader config snapshot (dashboard process)</h3>
      <dl class="sv-dl">${modelDl}</dl>
    </section>`;
}

function fillCycleSelect(files) {
  const sel = document.getElementById("sv-cycle-select");
  const keep = sel.value;
  sel.innerHTML = '<option value="">— choose —</option>';
  for (const row of files || []) {
    if (!row.cycle_id) continue;
    const o = document.createElement("option");
    o.value = String(row.cycle_id);
    o.textContent = `#${row.cycle_id} · ${row.filename}`;
    sel.appendChild(o);
  }
  const ok = Array.from(sel.options).some((o) => o.value === keep);
  if (ok) sel.value = keep;
}

function renderLogTable(files) {
  const tbody = (files || [])
    .map((r) => {
      const cid = r.cycle_id || 0;
      return `<tr>
        <td><code>${cid}</code></td>
        <td class="muted mono-xs">${escapeHtml(r.filename)}</td>
        <td>${fmtBytes(r.bytes)}</td>
        <td><button type="button" class="link-btn" data-cycle="${cid}">Inspect</button></td></tr>`;
    })
    .join("");
  document.getElementById("sv-log-table").innerHTML = `
    <div class="sv-scroll sv-table-wrap">
      <table><thead><tr><th>Cycle</th><th>Filename</th><th>Size</th><th></th></tr></thead>
      <tbody>${tbody || `<tr><td colspan="4" class="muted">No cycle_*.json files found.</td></tr>`}</tbody></table></div>`;
}

function formatPromptSectionBody(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    const meta = [];
    if (v.chars != null) meta.push(`${v.chars} chars`);
    const prev = v.preview != null ? String(v.preview) : "";
    const full = v.full != null ? String(v.full) : "";
    const head = meta.length ? `# ${meta.join(", ")}\n\n` : "";
    if (full && full.trim() !== prev.trim()) return `${head}${prev}\n\n—— full ——\n\n${full}`;
    return head + prev;
  }
  return JSON.stringify(v, null, 2);
}

function renderInspect(data) {
  const root = document.getElementById("sv-inspect");
  const log = data.cycle_log;
  const strip = !!data.strip_full_prompts;

  let decHtml = "";
  for (const d of data.decisions || []) {
    const mj =
      d.model_json != null
        ? `<details><summary><code>model_json</code></summary><pre class="rationale-pre">${escapeHtml(
            JSON.stringify(d.model_json, null, 2)
          )}</pre></details>`
        : "";
    decHtml += `<tr><td>${escapeHtml(String(d.kind))}</td><td>${escapeHtml(d.company_label || d.symbol || "—")}</td>
      <td>${escapeHtml(String(d.side || "—"))}</td><td>${d.executed ? "yes" : "no"}</td>
      <td><pre class="rationale-pre tight">${escapeHtml((d.reason_he || "").slice(0, 4000))}</pre>${mj}</td></tr>`;
  }

  if (!log) {
    root.innerHTML = `
      <p class="muted">No cycle JSON on disk for <strong>#${data.cycle_id}</strong>.
      Trader may have logging disabled (<code>DEMO_TRADER_CYCLE_LOG_ENABLED=0</code>) or a different <code>DEMO_TRADER_CYCLE_LOG_DIR</code>.</p>
      <h3>SQLite decisions</h3><div class="sv-scroll sv-table-wrap"><table><thead><tr><th>kind</th><th>Issuer</th><th>side</th><th>exec</th><th>payload</th></tr></thead>
      <tbody>${decHtml || `<tr><td colspan="5" class="muted">No rows.</td></tr>`}</tbody></table></div>`;
    return;
  }

  const sections = ((log.prompt && log.prompt.sections) || {});
  let secBlocks = "";
  for (const [name, val] of Object.entries(sections)) {
    secBlocks += `<details><summary><code>${escapeHtml(name)}</code></summary><pre class="rationale-pre">${escapeHtml(
      formatPromptSectionBody(val)
    )}</pre></details>`;
  }

  const err = log.model_error ? `<h3>Error</h3><pre class="rationale-pre">${escapeHtml(String(log.model_error))}</pre>` : "";

  root.innerHTML = `
    <p><code>${escapeHtml(log._log_filename || "")}</code> · strip-full via API = <strong>${strip ? "yes" : "no"}</strong></p>
    <h3>Ingest</h3><pre class="rationale-pre">${escapeHtml(JSON.stringify(log.ingest || {}, null, 2))}</pre>
    <h3>Model response JSON</h3><pre class="rationale-pre">${escapeHtml(JSON.stringify(log.model_response ?? {}, null, 2))}</pre>
    ${err}
    <h3>Recorded executions stub</h3><pre class="rationale-pre">${escapeHtml(JSON.stringify(log.executions || [], null, 2))}</pre>
    <h3>Prompt blocks</h3>
    ${secBlocks || "<p class='muted'>No prompt sections parsed.</p>"}
    <h3>SQLite decisions sync</h3>
    <div class="sv-scroll sv-table-wrap"><table><thead><tr><th>kind</th><th>Name</th><th>side</th><th>exec</th><th>payload</th></tr></thead>
      <tbody>${decHtml}</tbody></table></div>`;
}

async function runInspect() {
  const sel = document.getElementById("sv-cycle-select");
  const id = parseInt(sel.value, 10);
  if (!id) {
    setSvStatus("Pick a cycle first.", true);
    return;
  }
  const strip = document.getElementById("sv-strip-full").checked;
  const q = `/api/supervision/cycle-inspect?cycle_id=${id}&strip_full_prompts=${strip ? "1" : "0"}`;
  setSvStatus("Loading inspector…");
  try {
    const data = await fetchJson(q);
    renderInspect(data);
    setSvStatus(`Loaded inspect for #${id}`);
  } catch (e) {
    setSvStatus(String(e), true);
  }
}

async function loadSupervision(force = false) {
  const overviewEl = document.getElementById("sv-overview");
  if (!overviewEl) return;
  if (!force && overviewEl.innerHTML.trim() !== "") {
    /* keep cache until explicit reload — still allow table updates */
  }
  setSvBanner("", false);
  setSvStatus("Loading overview…");
  try {
    const ov = await fetchJson("/api/supervision/overview?cycle_log_limit=120");
    renderSupervisionOverview(ov);
    renderLogTable(ov.cycle_logs);
    fillCycleSelect(ov.cycle_logs);
    setSvStatus(`Supervision refreshed ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    setSvBanner(`Supervision failed: ${e}`, true);
    overviewEl.innerHTML = `<p class="muted">Fix the errors above — often the Flask server’s working directory misses <code>data/trader.db</code>.</p>`;
    setSvStatus("", true);
  }
}

async function refreshMainData() {
  setStatus("Loading…");
  const days = daysParam();
  try {
    const promises = [
      fetchJson("/api/health"),
      fetchJson("/api/portfolio"),
      fetchJson(`/api/cycles?days=${days}`),
      fetchJson(`/api/knowledge?days=${days}${document.getElementById("maya-only").checked ? "&maya_only=1" : ""}`),
    ];
    if (activeTabId() === "supervision") {
      promises.push(fetchJson("/api/supervision/overview?cycle_log_limit=120"));
    }
    const bundle = await Promise.all(promises);
    let i = 0;
    const health = bundle[i++];
    const portfolio = bundle[i++];
    const cycles = bundle[i++];
    const knowledge = bundle[i++];
    if (!health.ok) setStatus("Missing trader.db and/or paper_state.json at configured paths.", true);
    else setStatus(`Dashboard data ${new Date().toLocaleTimeString()}`);
    renderPortfolio(portfolio);
    renderCycles(cycles);
    renderKnowledge(knowledge);
    if (activeTabId() === "supervision" && bundle[i]) {
      setSvBanner("", false);
      const ov = bundle[i];
      renderSupervisionOverview(ov);
      renderLogTable(ov.cycle_logs);
      fillCycleSelect(ov.cycle_logs);
    }
  } catch (e) {
    setStatus(String(e), true);
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
    });
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    setSvBanner("", false);
    if (btn.dataset.tab === "supervision") loadSupervision(true);
  });
});

document.getElementById("refresh").addEventListener("click", refreshMainData);
document.getElementById("days").addEventListener("change", refreshMainData);
document.getElementById("maya-only").addEventListener("change", refreshMainData);

const chk = document.getElementById("auto-refresh");
if (chk) chk.addEventListener("change", restartAutoRefresh);

const svReload = document.getElementById("sv-reload");
if (svReload) svReload.addEventListener("click", () => loadSupervision(true));
const inspectBtn = document.getElementById("sv-inspect-btn");
if (inspectBtn) inspectBtn.addEventListener("click", runInspect);

const logTbl = document.getElementById("sv-log-table");
if (logTbl) {
  logTbl.addEventListener("click", (ev) => {
    const tgt = ev.target.closest("button[data-cycle]");
    if (!tgt) return;
    document.getElementById("sv-cycle-select").value = tgt.getAttribute("data-cycle");
    runInspect();
  });
}

refreshMainData();
restartAutoRefresh();
