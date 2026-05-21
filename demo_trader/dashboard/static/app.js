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

function daysParam() {
  return document.getElementById("days").value;
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
        `<tr><td>${row.symbol}</td><td>${row.qty}</td><td>${row.last_price ?? "—"}</td><td>${fmtIls(row.market_value_ils)}</td></tr>`
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
            return `<div class="action"><span class="side-${side}">${a.side} ${a.symbol} ×${a.qty}</span> — ${a.reason_he || ""}</div>`;
          }
          if (a.type === "blocked") {
            return `<div class="action">⏸ Blocked ${a.side || ""} ${a.symbol || ""} — ${a.reason_he || "after hours"}</div>`;
          }
          if (a.type === "hold") {
            return `<div class="action">Hold — ${a.reason_he || ""}</div>`;
          }
          return `<div class="action">${a.type} ${a.symbol || ""} — ${a.reason_he || ""}</div>`;
        })
        .join("");
      const summary = c.summary_he ? `<p class="muted">${c.summary_he}</p>` : "";
      return `
        <article class="cycle">
          <div class="cycle-head">
            <span class="ts">#${c.cycle_id} · ${c.ts}</span>
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
          <h3>${title}</h3>
          <div class="k-meta">${k.event_time || k.ts} · ${k.source} · ${k.matched_symbol || "—"}
            · ${k.sentiment || "—"} · ${k.trade_usefulness || "—"} ${flash}</div>
          <p class="k-summary">${sum}</p>
          ${k.url ? `<p class="muted"><a href="${k.url}" target="_blank" rel="noopener">source</a></p>` : ""}
        </article>`;
    })
    .join("");
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
  });
});

document.getElementById("refresh").addEventListener("click", refresh);
document.getElementById("days").addEventListener("change", refresh);
document.getElementById("maya-only").addEventListener("change", refresh);
refresh();
setInterval(refresh, 60_000);
