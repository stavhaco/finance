const BAR_COLORS = ["#3d8bfd", "#3dd68c", "#f0b429", "#b388ff", "#ff7eb9", "#6ee7b7", "#8899aa"];
const PAGE_CYCLES = 100;
const PAGE_KNOWLEDGE = 200;
const PAGE_SV_LOGS = 250;
let refreshTimerId = null;
let cyclesState = { items: [], total: 0, offset: 0, hasMore: false };
let knowledgeState = { items: [], total: 0, offset: 0, hasMore: false };
let svLogsState = { items: [], total: 0, offset: 0, hasMore: false };

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

function daysQuery() {
  const d = daysParam();
  return d === "all" ? "all" : d;
}

function setListMeta(elId, shown, total, label) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (!total) {
    el.textContent = `No ${label} in this timeframe.`;
    return;
  }
  el.textContent =
    shown >= total
      ? `Showing all ${total} ${label}.`
      : `Showing ${shown} of ${total} ${label} (newest first).`;
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
  const fast = document.getElementById("fast-refresh");
  const ms = fast && fast.checked ? 30_000 : 120_000;
  refreshTimerId = setInterval(refreshMainData, ms);
}

function renderOpsStrip(status) {
  const el = document.getElementById("ops-strip");
  if (!el || !status) return;
  const lc = status.last_cycle || {};
  const ej = status.enrichment_jobs || {};
  const alerts = status.alerts || [];
  const alertHtml =
    alerts.length === 0
      ? `<span class="ops-pill ok">No alerts</span>`
      : alerts
          .slice(0, 4)
          .map((a) => `<span class="ops-pill ${escapeHtml(a.level)}">${escapeHtml(a.message)}</span>`)
          .join("");
  const ollamaCls = status.ollama_ok ? "ok" : "error";
  const taseCls = status.tase_trading_open ? "ok" : "muted";
  el.innerHTML = `
    <span class="ops-pill ${ollamaCls}">Ollama ${status.ollama_ok ? "up" : "down"}</span>
    <span class="ops-pill ${taseCls}">TASE ${status.tase_trading_open ? "open" : "closed"}</span>
    <span class="ops-pill">Cycle #${escapeHtml(String(lc.id || "—"))} · NAV ${fmtIls(lc.nav_ils)} · α ${fmtPct(lc.alpha_pct, false)}</span>
    <span class="ops-pill">Enrich Q: ${Number(ej.pending || 0)} pending</span>
    <span class="ops-pill muted">${escapeHtml(status.prompt_version || "")}</span>
    ${alertHtml}`;
}

function parseChartTs(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d.getTime();
}

function resizeNavCanvas(canvas) {
  const rect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: 900 };
  const cssW = Math.max(320, Math.floor(rect.width || 900));
  const cssH = 180;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(cssW * dpr);
  canvas.height = Math.floor(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: cssW, h: cssH };
}

function renderNavChart(series) {
  const canvas = document.getElementById("nav-chart");
  if (!canvas) return;
  const legend = document.getElementById("nav-chart-legend");
  if (!series || !series.points || series.points.length < 2) {
    const { ctx, w, h } = resizeNavCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#8b9cb3";
    ctx.font = "12px system-ui";
    ctx.fillText("Not enough cycle data yet", 12, 24);
    if (legend) legend.textContent = "";
    return;
  }

  const raw = series.points
    .filter((p) => p.nav_ils != null && parseChartTs(p.ts) != null)
    .map((p) => ({
      t: parseChartTs(p.ts),
      nav: Number(p.nav_ils),
      ret: p.portfolio_return_pct == null ? null : Number(p.portfolio_return_pct),
      alpha: p.alpha_pct == null ? null : Number(p.alpha_pct),
    }))
    .sort((a, b) => a.t - b.t);

  if (raw.length < 2) return;

  const { ctx, w, h } = resizeNavCanvas(canvas);
  const pad = { l: 52, r: 52, t: 16, b: 32 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;

  const tMin = raw[0].t;
  const tMax = raw[raw.length - 1].t;
  const tSpan = tMax - tMin || 1;

  const navs = raw.map((p) => p.nav);
  let minN = Math.min(...navs);
  let maxN = Math.max(...navs);
  let navSpan = maxN - minN;
  const meanN = navs.reduce((a, b) => a + b, 0) / navs.length;
  const navFlat = navSpan < Math.max(200, meanN * 0.002);

  const rets = raw.map((p) => p.ret).filter((v) => v != null && !Number.isNaN(v));
  const useReturn = navFlat && rets.length >= 2;
  let minY;
  let maxY;
  let yLabel;
  let yValues;
  if (useReturn) {
    yValues = raw.map((p) => (p.ret == null || Number.isNaN(p.ret) ? null : p.ret));
    minY = Math.min(...rets);
    maxY = Math.max(...rets);
    yLabel = "%";
  } else {
    yValues = navs;
    minY = minN;
    maxY = maxN;
    yLabel = "₪";
    if (navSpan < Math.max(500, meanN * 0.01)) {
      const padN = Math.max(500, meanN * 0.01);
      minN = meanN - padN;
      maxN = meanN + padN;
      navSpan = maxN - minN;
    } else {
      const margin = navSpan * 0.08;
      minN -= margin;
      maxN += margin;
      navSpan = maxN - minN;
    }
    minY = minN;
    maxY = maxN;
  }
  const ySpan = maxY - minY || 1;

  const xAt = (t) => pad.l + ((t - tMin) / tSpan) * plotW;
  const yAt = (v) => pad.t + plotH - ((v - minY) / ySpan) * plotH;

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#1a2332";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "#2a3548";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(w - pad.r, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "#3d8bfd";
  ctx.lineWidth = 2;
  ctx.beginPath();
  let started = false;
  raw.forEach((p, i) => {
    const v = useReturn ? yValues[i] : p.nav;
    if (v == null || Number.isNaN(v)) return;
    const x = xAt(p.t);
    const y = yAt(v);
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else ctx.lineTo(x, y);
  });
  ctx.stroke();

  if (!useReturn && rets.length >= 2) {
    const minR = Math.min(...rets);
    const maxR = Math.max(...rets);
    const rSpan = maxR - minR || 1;
    ctx.strokeStyle = "#3dd68c";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    started = false;
    raw.forEach((p) => {
      if (p.ret == null || Number.isNaN(p.ret)) return;
      const x = xAt(p.t);
      const y = pad.t + plotH - ((p.ret - minR) / rSpan) * plotH;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.fillStyle = "#8b9cb3";
  ctx.font = "11px system-ui";
  if (useReturn) {
    ctx.fillText(`${minY.toFixed(2)}%`, 4, h - pad.b);
    ctx.fillText(`${maxY.toFixed(2)}%`, 4, pad.t + 10);
  } else {
    ctx.fillText(fmtIls(minY), 4, h - pad.b);
    ctx.fillText(fmtIls(maxY), 4, pad.t + 10);
    if (rets.length >= 2) {
      ctx.textAlign = "right";
      ctx.fillText("ret %", w - 4, pad.t + 10);
      ctx.textAlign = "left";
    }
  }

  if (legend) {
    legend.textContent = useReturn
      ? "Blue: portfolio return % (NAV flat in window — showing return instead)"
      : "Blue: NAV (₪) · Green dashed: portfolio return %";
  }
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

function actionReasonHtml(a) {
  const en = (a.display_en || a.display_text || "").trim();
  const note = (a.display_note || "").trim();
  if (en) {
    return `<div class="why-en narr-ltr">${nl2brEscaped(en)}</div>`;
  }
  if (note) {
    return `<p class="muted action-note">${escapeHtml(note)}</p>`;
  }
  return `<p class="muted action-note">No English rationale stored for this action.</p>`;
}

function citedArticlesBlock(articles) {
  const rows = Array.isArray(articles) ? articles : [];
  if (!rows.length) return "";
  return `<details class="cited-wrap"><summary>News cited this cycle (${rows.length})</summary><div class="cited-articles-grid">${rows
    .map((art) => {
      const title = escapeHtml(art.title_en || "(no title)");
      const src = escapeHtml(String(art.source || ""));
      const sym = escapeHtml(String(art.matched_company_label || art.matched_symbol || ""));
      const sum = escapeHtml(String(art.executive_summary_en || "").slice(0, 280));
      const url =
        art.url && String(art.url).startsWith("http")
          ? ` · <a href="${escapeHtml(art.url)}" target="_blank" rel="noopener">source</a>`
          : "";
      return `<article class="cited-article-card"><div class="cited-article-head"><span class="sv-pill">#${escapeHtml(
        String(art.id)
      )}</span> ${src}${url}</div><h4 class="cited-article-title">${title}</h4>${sym ? `<div class="muted mono-sm">${sym}</div>` : ""}${
        sum ? `<p class="cited-article-sum">${sum}</p>` : ""
      }</article>`;
    })
    .join("")}</div></details>`;
}

function cycleCardHtml(c) {
  const openCls = c.market_open ? "open" : "closed";
  const openLbl = c.market_open ? "Market open" : "Market closed";
  const perf = `Portfolio ${fmtPct(c.portfolio_return_pct)} · TA-35 ${fmtPct(c.benchmark_return_pct)} · α ${fmtPct(c.alpha_pct)}`;
  const benchLbl = c.benchmark_label ? ` · bench: ${escapeHtml(c.benchmark_label)}` : "";
  const nar = (c.summary_en || "").trim();
  const citedBlock = citedArticlesBlock(c.cited_articles);
  const narrBlock =
    nar.length === 0
      ? ""
      : `<details class="cycle-narr"><summary>Model summary</summary><div class="why-en narr-block narr-ltr">${nl2brEscaped(
          nar
        )}</div></details>`;
  const actions = (c.actions || [])
    .map((a) => {
      const rlBlock = actionReasonHtml(a);
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
      ${citedBlock}
      ${narrBlock}
      ${actions || "<p class='muted'>Nothing recorded this cycle.</p>"}
    </article>`;
}

function renderCyclesFromState() {
  const root = document.getElementById("cycles-list");
  const moreBtn = document.getElementById("cycles-more");
  const cycles = cyclesState.items;
  setListMeta("cycles-meta", cycles.length, cyclesState.total, "cycles");
  if (!cycles.length) {
    root.innerHTML = "<p class='muted'>No cycles in this timeframe.</p>";
  } else {
    root.innerHTML = cycles.map(cycleCardHtml).join("");
  }
  if (moreBtn) moreBtn.hidden = !cyclesState.hasMore;
}

function knowledgeCardHtml(k) {
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
}

function renderKnowledgeFromState() {
  const root = document.getElementById("knowledge-list");
  const moreBtn = document.getElementById("knowledge-more");
  const items = knowledgeState.items;
  setListMeta("knowledge-meta", items.length, knowledgeState.total, "knowledge events");
  if (!items.length) {
    root.innerHTML = "<p class='muted'>No knowledge events in this timeframe.</p>";
  } else {
    root.innerHTML = items.map(knowledgeCardHtml).join("");
  }
  if (moreBtn) moreBtn.hidden = !knowledgeState.hasMore;
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
  const seen = new Set();
  sel.innerHTML = '<option value="">— choose —</option>';
  for (const row of files || []) {
    if (!row.cycle_id || seen.has(row.cycle_id)) continue;
    seen.add(row.cycle_id);
    const o = document.createElement("option");
    o.value = String(row.cycle_id);
    o.textContent = `#${row.cycle_id} · ${row.filename}`;
    sel.appendChild(o);
  }
  const ok = Array.from(sel.options).some((o) => o.value === keep);
  if (ok) sel.value = keep;
}

function applySupervisionLogs(ov, { append = false } = {}) {
  const paths = ov.paths || {};
  const batch = ov.cycle_logs || [];
  const total = Number(paths.cycle_log_file_count || 0);
  const offset = Number(paths.cycle_logs_offset || 0);
  if (append) {
    svLogsState.items = svLogsState.items.concat(batch);
  } else {
    svLogsState.items = batch.slice();
  }
  svLogsState.total = total;
  svLogsState.offset = offset + batch.length;
  svLogsState.hasMore = !!paths.cycle_logs_has_more;
  setListMeta("sv-log-meta", svLogsState.items.length, svLogsState.total, "cycle log files");
  renderLogTable(svLogsState.items);
  fillCycleSelect(svLogsState.items);
  const moreBtn = document.getElementById("sv-logs-more");
  if (moreBtn) moreBtn.hidden = !svLogsState.hasMore;
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
    const ov = await fetchJson(`/api/supervision/overview?cycle_log_limit=${PAGE_SV_LOGS}&cycle_log_offset=0`);
    renderSupervisionOverview(ov);
    applySupervisionLogs(ov, { append: false });
    setSvStatus(`Supervision refreshed ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    setSvBanner(`Supervision failed: ${e}`, true);
    overviewEl.innerHTML = `<p class="muted">Fix the errors above — often the Flask server’s working directory misses <code>data/trader.db</code>.</p>`;
    setSvStatus("", true);
  }
}

async function loadMoreSvLogs() {
  if (!svLogsState.hasMore) return;
  setSvStatus("Loading more log files…");
  try {
    const ov = await fetchJson(
      `/api/supervision/overview?cycle_log_limit=${PAGE_SV_LOGS}&cycle_log_offset=${svLogsState.offset}`
    );
    applySupervisionLogs(ov, { append: true });
    setSvStatus(`Showing ${svLogsState.items.length} of ${svLogsState.total} log files`);
  } catch (e) {
    setSvStatus(String(e), true);
  }
}

function applyCyclesPayload(data, { append = false } = {}) {
  const batch = data.cycles || [];
  if (append) cyclesState.items = cyclesState.items.concat(batch);
  else cyclesState.items = batch.slice();
  cyclesState.total = Number(data.total || 0);
  cyclesState.offset = Number(data.offset || 0) + batch.length;
  cyclesState.hasMore = !!data.has_more;
  renderCyclesFromState();
}

function applyKnowledgePayload(data, { append = false } = {}) {
  const batch = data.items || [];
  if (append) knowledgeState.items = knowledgeState.items.concat(batch);
  else knowledgeState.items = batch.slice();
  knowledgeState.total = Number(data.total || 0);
  knowledgeState.offset = Number(data.offset || 0) + batch.length;
  knowledgeState.hasMore = !!data.has_more;
  renderKnowledgeFromState();
}

async function loadMoreCycles() {
  if (!cyclesState.hasMore) return;
  const days = daysQuery();
  const data = await fetchJson(`/api/cycles?days=${days}&limit=${PAGE_CYCLES}&offset=${cyclesState.offset}`);
  applyCyclesPayload(data, { append: true });
}

async function loadMoreKnowledge() {
  if (!knowledgeState.hasMore) return;
  const days = daysQuery();
  const maya = document.getElementById("maya-only").checked ? "&maya_only=1" : "";
  const data = await fetchJson(
    `/api/knowledge?days=${days}&limit=${PAGE_KNOWLEDGE}&offset=${knowledgeState.offset}${maya}`
  );
  applyKnowledgePayload(data, { append: true });
}

async function refreshMainData() {
  setStatus("Loading…");
  const days = daysQuery();
  const navDays = days === "all" ? "3650" : days;
  try {
    const promises = [
      fetchJson("/api/health"),
      fetchJson("/api/status"),
      fetchJson("/api/portfolio"),
      fetchJson(`/api/series/nav?days=${navDays}`),
      fetchJson(`/api/cycles?days=${days}&limit=${PAGE_CYCLES}&offset=0`),
      fetchJson(
        `/api/knowledge?days=${days}&limit=${PAGE_KNOWLEDGE}&offset=0${
          document.getElementById("maya-only").checked ? "&maya_only=1" : ""
        }`
      ),
    ];
    if (activeTabId() === "supervision") {
      promises.push(fetchJson(`/api/supervision/overview?cycle_log_limit=${PAGE_SV_LOGS}&cycle_log_offset=0`));
    }
    const bundle = await Promise.all(promises);
    let i = 0;
    const health = bundle[i++];
    const opsStatus = bundle[i++];
    const portfolio = bundle[i++];
    const navSeries = bundle[i++];
    const cycles = bundle[i++];
    const knowledge = bundle[i++];
    if (!health.ok) setStatus("Missing trader.db and/or paper_state.json at configured paths.", true);
    else setStatus(`Dashboard data ${new Date().toLocaleTimeString()}`);
    renderOpsStrip(opsStatus);
    const canvas = document.getElementById("nav-chart");
    if (canvas) canvas.dataset.lastSeries = JSON.stringify(navSeries);
    renderNavChart(navSeries);
    renderPortfolio(portfolio);
    applyCyclesPayload(cycles, { append: false });
    applyKnowledgePayload(knowledge, { append: false });
    if (activeTabId() === "supervision" && bundle[i]) {
      setSvBanner("", false);
      const ov = bundle[i];
      renderSupervisionOverview(ov);
      applySupervisionLogs(ov, { append: false });
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
const fastChk = document.getElementById("fast-refresh");
if (fastChk) fastChk.addEventListener("change", restartAutoRefresh);

const svReload = document.getElementById("sv-reload");
if (svReload) svReload.addEventListener("click", () => loadSupervision(true));
const inspectBtn = document.getElementById("sv-inspect-btn");
if (inspectBtn) inspectBtn.addEventListener("click", runInspect);
const cyclesMore = document.getElementById("cycles-more");
if (cyclesMore) cyclesMore.addEventListener("click", () => loadMoreCycles().catch((e) => setStatus(String(e), true)));
const knowledgeMore = document.getElementById("knowledge-more");
if (knowledgeMore)
  knowledgeMore.addEventListener("click", () => loadMoreKnowledge().catch((e) => setStatus(String(e), true)));
const svLogsMore = document.getElementById("sv-logs-more");
if (svLogsMore) svLogsMore.addEventListener("click", () => loadMoreSvLogs());

const logTbl = document.getElementById("sv-log-table");
if (logTbl) {
  logTbl.addEventListener("click", (ev) => {
    const tgt = ev.target.closest("button[data-cycle]");
    if (!tgt) return;
    document.getElementById("sv-cycle-select").value = tgt.getAttribute("data-cycle");
    runInspect();
  });
}

window.addEventListener("resize", () => {
  const canvas = document.getElementById("nav-chart");
  if (canvas && canvas.dataset.lastSeries) {
    try {
      renderNavChart(JSON.parse(canvas.dataset.lastSeries));
    } catch (_) {
      /* ignore */
    }
  }
});

refreshMainData();
restartAutoRefresh();
