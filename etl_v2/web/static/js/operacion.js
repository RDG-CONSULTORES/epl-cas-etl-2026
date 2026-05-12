// ============================================================
// Operación Diaria EPL CAS — dashboard JS (vanilla)
// ============================================================

const API = "/api/operacion";

const state = {
    tipo: "week",
    offset: 0,
    rankingScope: "go",
};

// --------------------------------------------------------------
// Theme sync con dashboard de supervisiones (localStorage 'data-theme')
// --------------------------------------------------------------
function initTheme() {
    const saved = localStorage.getItem("data-theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    document.getElementById("theme-toggle").addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        const next = cur === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("data-theme", next);
    });
}

// --------------------------------------------------------------
// Period bar
// --------------------------------------------------------------
function initPeriodBar() {
    const bar = document.getElementById("period-bar");
    bar.addEventListener("click", (e) => {
        const btn = e.target.closest(".period-btn");
        if (!btn) return;
        bar.querySelectorAll(".period-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.tipo = btn.dataset.tipo;
        state.offset = parseInt(btn.dataset.offset, 10);
        refresh();
    });
}

function getPeriodoQuery() {
    if (state.tipo === "week" && state.offset === 0)  return "current-week";
    if (state.tipo === "week" && state.offset === -1) return "prev-week";
    if (state.tipo === "month")                       return "current-month";
    return "current-week";
}

// --------------------------------------------------------------
// Fetch helper
// --------------------------------------------------------------
async function api(path) {
    const res = await fetch(API + path);
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
}

// --------------------------------------------------------------
// KPIs
// --------------------------------------------------------------
async function loadKpis() {
    const data = await api(`/kpis?periodo=${getPeriodoQuery()}`);
    const overall = data.overall;
    const el = document.getElementById("kpi-overall-value");
    el.textContent = `${overall.pct_compliance}%`;
    el.className = "kpi-value " + colorClass(overall.pct_compliance);
    document.getElementById("kpi-overall-sub").textContent =
        `${overall.n_on_time} ✓ · ${overall.n_late} late · ${overall.n_missed} missed`;
    for (const f of data.per_form) {
        const node = document.querySelector(`[data-kpi="${f.form_key}"]`);
        if (node) {
            node.textContent = `${f.pct_compliance}%`;
            node.className = "kpi-value " + colorClass(f.pct_compliance);
        }
    }
}

function colorClass(pct) {
    if (pct >= 90) return "good";
    if (pct >= 70) return "warn";
    return "bad";
}

// --------------------------------------------------------------
// Ranking
// --------------------------------------------------------------
async function loadRanking() {
    const data = await api(`/ranking?scope=${state.rankingScope}&periodo=${getPeriodoQuery()}`);
    const list = document.getElementById("ranking-list");
    list.innerHTML = "";
    for (const item of data.items) {
        const row = document.createElement("div");
        row.className = "ranking-row";
        row.dataset.id = item.id;
        row.dataset.scope = state.rankingScope;
        const sub = state.rankingScope === "go"
            ? `${item.n_sucursales} sucursales`
            : (item.go_nombre || "");
        row.innerHTML = `
            <span class="ranking-rank">${item.rank}</span>
            <div>
                <div class="ranking-name">${escapeHtml(item.nombre || "—")}</div>
                <div class="ranking-sub">${escapeHtml(sub)}</div>
            </div>
            <span class="ranking-pct ${colorClass(item.pct_compliance)}">${item.pct_compliance}%</span>
        `;
        row.addEventListener("click", () => openDrillDown(state.rankingScope, item.id, item.nombre));
        list.appendChild(row);
    }
    document.getElementById("toggle-ranking-scope").textContent =
        state.rankingScope === "go" ? "Ver sucursales →" : "← Ver grupos";
}

// --------------------------------------------------------------
// Heatmap
// --------------------------------------------------------------
async function loadHeatmap() {
    const data = await api(`/heatmap?periodo=${getPeriodoQuery()}`);
    const wrap = document.getElementById("heatmap-wrapper");
    const bySuc = {};
    const dayKeys = new Set();
    for (const c of data.cells) {
        if (!bySuc[c.location_id]) bySuc[c.location_id] = { nombre: c.sucursal, cells: {} };
        if (c.day) {
            dayKeys.add(c.day);
            bySuc[c.location_id].cells[`${c.day}__${c.form_key}`] = c.status;
        }
    }
    const days = Array.from(dayKeys).sort();
    let html = `<table class="heatmap-table"><thead><tr><th>Sucursal</th>`;
    for (const d of days) html += `<th colspan="3">${formatDay(d)}</th>`;
    html += "</tr></thead><tbody>";
    for (const sid of Object.keys(bySuc)) {
        html += `<tr><th>${escapeHtml(bySuc[sid].nombre)}</th>`;
        for (const d of days) {
            for (const fk of ["apertura", "entrega", "cierre"]) {
                const s = bySuc[sid].cells[`${d}__${fk}`] || "";
                html += `<td class="cell ${s}" title="${d} ${fk}: ${s || "—"}"></td>`;
            }
        }
        html += "</tr>";
    }
    html += "</tbody></table>";
    wrap.innerHTML = html;
}

function formatDay(iso) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("es-MX", { weekday: "short", day: "numeric" });
}

// --------------------------------------------------------------
// Histórico (8 semanas)
// --------------------------------------------------------------
async function loadHistorico() {
    const data = await api(`/historico?scope=global&semanas=8&form_key=overall`);
    const wrap = document.getElementById("trend-wrapper");
    if (!data.items.length) { wrap.innerHTML = "<small>Sin datos aún.</small>"; return; }
    const max = 100;
    wrap.innerHTML = data.items.map(i => `
        <div class="trend-bar" style="height: ${(i.pct_compliance / max) * 100}%">
            <span class="trend-bar-label">${i.week_start.slice(5)} · ${i.pct_compliance.toFixed(0)}%</span>
        </div>
    `).join("");
}

// --------------------------------------------------------------
// Alertas
// --------------------------------------------------------------
async function loadAlertas() {
    const data = await api(`/alertas`);
    const wrap = document.getElementById("alertas-content");
    const bajo = data.bajo_compliance.length
        ? data.bajo_compliance.slice(0, 5).map(b => `
            <div class="alert-row">
                <div>
                    <div class="ranking-name">${escapeHtml(b.nombre)}</div>
                    <div class="ranking-sub">${escapeHtml(b.go_nombre || "")}</div>
                </div>
                <span class="alert-badge">${b.pct_compliance}%</span>
            </div>`).join("")
        : "<small>Sin alertas de bajo cumplimiento.</small>";
    const pend = data.pendientes_hoy.length
        ? `<p style="margin-top:12px;color:var(--color-text-secondary);font-size:13px">
             Pendientes hoy: ${data.pendientes_hoy.length}</p>`
        : "";
    wrap.innerHTML = bajo + pend;
}

// --------------------------------------------------------------
// Drill-down modal
// --------------------------------------------------------------
async function openDrillDown(scope, id, nombre) {
    showModal(`<h2>${escapeHtml(nombre || "")}</h2><p>Cargando…</p>`);
    try {
        const path = scope === "go" ? `/grupo/${id}` : `/sucursal/${id}`;
        const data = await api(`${path}?periodo=${getPeriodoQuery()}`);
        const html = scope === "go" ? renderGrupoDetail(data) : renderSucursalDetail(data);
        document.getElementById("modal-content").innerHTML = html;
        // Click en sucursal del modal de GO → abre drill-down de sucursal
        document.querySelectorAll("[data-suc-id]").forEach(el => {
            el.addEventListener("click", () => {
                openDrillDown("sucursal", parseInt(el.dataset.sucId, 10), el.dataset.sucName);
            });
        });
    } catch (e) {
        document.getElementById("modal-content").innerHTML = `<p>Error: ${e.message}</p>`;
    }
}

function renderGrupoDetail(d) {
    const o = d.overall;
    const sucs = d.sucursales.map(s => `
        <div class="ranking-row" data-suc-id="${s.location_id}" data-suc-name="${escapeHtml(s.nombre)}">
            <span class="ranking-rank">·</span>
            <div><div class="ranking-name">${escapeHtml(s.nombre)}</div></div>
            <span class="ranking-pct ${colorClass(s.pct_compliance)}">${s.pct_compliance}%</span>
        </div>`).join("");
    return `
        <h2>${escapeHtml(d.grupo.nombre)}</h2>
        <p class="kpi-sub">${d.start} → ${d.end}</p>
        <div class="kpi-value ${colorClass(o.pct_compliance)}">${o.pct_compliance}%</div>
        <p class="kpi-sub">${o.n_on_time} ✓ · ${o.n_late} late · ${o.n_missed} missed</p>
        <h3 style="margin-top:24px">Sucursales</h3>
        ${sucs}
    `;
}

function renderSucursalDetail(d) {
    const days = d.days.map(day => {
        const forms = ["apertura", "entrega", "cierre"].map(fk => {
            const f = day.forms[fk];
            if (!f) return `<td class="cell missed" title="${fk}: missed"></td>`;
            return `<td class="cell ${f.status}" title="${fk}: ${f.status}"></td>`;
        }).join("");
        return `<tr><th>${formatDay(day.day)}</th>${forms}<td>${day.pct_day}%</td></tr>`;
    }).join("");
    return `
        <h2>${escapeHtml(d.sucursal.nombre)}</h2>
        <p class="kpi-sub">${escapeHtml(d.sucursal.go_nombre || "")} · ${d.start} → ${d.end}</p>
        <table class="heatmap-table" style="margin-top:16px">
            <thead><tr><th>Día</th><th>Aper</th><th>Ent</th><th>Cier</th><th>Día %</th></tr></thead>
            <tbody>${days}</tbody>
        </table>
    `;
}

function showModal(html) {
    document.getElementById("modal-content").innerHTML = html;
    document.getElementById("modal-backdrop").hidden = false;
    document.body.classList.add("scroll-locked");
}

function closeModal() {
    document.getElementById("modal-backdrop").hidden = true;
    document.body.classList.remove("scroll-locked");
}

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
});

// --------------------------------------------------------------
// Ranking scope toggle
// --------------------------------------------------------------
document.getElementById("toggle-ranking-scope").addEventListener("click", () => {
    state.rankingScope = state.rankingScope === "go" ? "sucursal" : "go";
    loadRanking();
});

// --------------------------------------------------------------
// Pull-to-refresh (touch)
// --------------------------------------------------------------
function initPullToRefresh() {
    const ind = document.getElementById("ptr-indicator");
    let startY = 0, pulling = false;
    document.addEventListener("touchstart", (e) => {
        if (window.scrollY === 0) { startY = e.touches[0].clientY; pulling = true; }
    }, { passive: true });
    document.addEventListener("touchmove", (e) => {
        if (!pulling) return;
        const delta = e.touches[0].clientY - startY;
        if (delta > 60) ind.classList.add("visible");
        else ind.classList.remove("visible");
    }, { passive: true });
    document.addEventListener("touchend", () => {
        if (ind.classList.contains("visible")) refresh();
        ind.classList.remove("visible");
        pulling = false;
    });
}

// --------------------------------------------------------------
// Helpers
// --------------------------------------------------------------
function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[c]);
}

async function refresh() {
    try {
        await Promise.all([loadKpis(), loadRanking(), loadHeatmap(), loadHistorico(), loadAlertas()]);
    } catch (e) {
        console.error(e);
    }
}

// --------------------------------------------------------------
// Init
// --------------------------------------------------------------
initTheme();
initPeriodBar();
initPullToRefresh();
refresh();
setInterval(refresh, 60_000);
