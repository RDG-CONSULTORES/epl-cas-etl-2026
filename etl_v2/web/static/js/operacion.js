// ============================================================
// Operación Diaria EPL CAS — JS vanilla, mockup-aligned
// ============================================================
const API = "/api/operacion";

const state = {
    tipo: "week",
    offset: 0,
    rankingScope: "go",
};

// ---------------- Theme ----------------
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

// ---------------- Period (main toggle) ----------------
function initToggle() {
    document.getElementById("main-toggle").addEventListener("click", (e) => {
        const btn = e.target.closest(".toggle-btn");
        if (!btn) return;
        if (btn.dataset.tipo === "hist") {
            openHistoricoModal();
            return;
        }
        document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("active"));
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

// ---------------- API helper ----------------
async function api(path) {
    const res = await fetch(API + path);
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
}

// ---------------- Color helpers ----------------
function pctClass(pct) {
    if (pct >= 85) return "pct-excellent";
    if (pct >= 65) return "pct-good";
    if (pct >= 50) return "pct-regular";
    return "pct-critical";
}
function heatClass(pct) {
    if (pct == null) return "heat-empty";
    if (pct >= 85) return "heat-excellent";
    if (pct >= 65) return "heat-good";
    if (pct >= 50) return "heat-regular";
    return "heat-critical";
}

// ---------------- Period bar ----------------
async function loadPeriod() {
    const tipo = state.tipo === "month" ? "month" : "week";
    const offset = state.offset;
    const data = await api(`/periodo?tipo=${tipo}&offset=${offset}`);
    document.getElementById("period-range").textContent = formatRange(data.start, data.end);

    // progress text: x/n (días transcurridos / total) si is_current
    const start = new Date(data.start + "T00:00:00");
    const end = new Date(data.end + "T00:00:00");
    const today = new Date(data.today + "T00:00:00");
    const totalDays = Math.round((end - start) / 86400000) + 1;
    const elapsed = Math.min(Math.max(Math.floor((today - start) / 86400000) + 1, 0), totalDays);
    const progressText = data.is_current ? `${elapsed}/${totalDays}` : `${totalDays}/${totalDays}`;
    document.getElementById("period-progress-text").textContent = progressText;
}

function formatRange(startISO, endISO) {
    const months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
    const s = new Date(startISO + "T00:00:00");
    const e = new Date(endISO + "T00:00:00");
    if (s.getMonth() === e.getMonth()) {
        return `${s.getDate()} — ${e.getDate()} ${months[e.getMonth()]}`;
    }
    return `${s.getDate()} ${months[s.getMonth()]} — ${e.getDate()} ${months[e.getMonth()]}`;
}

// ---------------- KPIs ----------------
async function loadKpis() {
    const data = await api(`/kpis?periodo=${getPeriodoQuery()}`);
    const o = data.overall;
    const valEl = document.getElementById("kpi-overall-value");
    valEl.textContent = `${o.pct_compliance.toFixed(1)}%`;

    // Delta vs periodo anterior (busco en weekly_summary via /historico)
    try {
        const hist = await api(`/historico?scope=global&semanas=2&form_key=overall`);
        const items = hist.items || [];
        const last = items[items.length - 1];
        const delta = last?.delta_prev_week;
        const deltaEl = document.getElementById("kpi-overall-delta");
        if (delta != null) {
            const sign = delta >= 0 ? "+" : "";
            deltaEl.textContent = `${sign}${delta.toFixed(1)} vs sem ant.`;
        } else {
            deltaEl.textContent = `${o.n_on_time} ✓ · ${o.n_late} ↺ · ${o.n_missed} ✗`;
        }
    } catch {
        document.getElementById("kpi-overall-delta").textContent =
            `${o.n_on_time} ✓ · ${o.n_late} ↺ · ${o.n_missed} ✗`;
    }

    // per_form: apertura/entrega/cierre
    for (const f of data.per_form) {
        const node = document.querySelector(`[data-form="${f.form_key}"]`);
        if (node) {
            node.textContent = `${f.pct_compliance.toFixed(1)}%`;
            node.className = "form-value " + pctClass(f.pct_compliance);
        }
    }
}

// ---------------- Heatmap día por día ----------------
async function loadHeatmap() {
    const data = await api(`/heatmap?periodo=${getPeriodoQuery()}`);
    const grid = document.getElementById("heat-grid");

    // organizar por sucursal_id → {day: {form_key: score}}
    // pero el mockup es por FORMULARIO (3 rows) × 7 DÍAS columns (con score % agregado del día)
    // Re-agregamos: por (día, form_key) → avg score
    const byDayForm = {};
    const days = new Set();
    const today = new Date().toISOString().slice(0, 10);
    for (const c of data.cells) {
        if (!c.day) continue;
        days.add(c.day);
        const key = `${c.day}__${c.form_key}`;
        if (!byDayForm[key]) byDayForm[key] = { sum: 0, n: 0 };
        if (c.score != null) {
            byDayForm[key].sum += c.score;
            byDayForm[key].n++;
        } else if (c.status === "missed") {
            byDayForm[key].n++;
        }
    }
    const sortedDays = Array.from(days).sort();

    // header
    let html = `<div></div>`;
    const dayLetters = ["D","L","M","X","J","V","S"];
    for (const d of sortedDays) {
        const dt = new Date(d + "T00:00:00");
        const letter = dayLetters[dt.getDay()];
        const isToday = d === today;
        html += `<div class="heat-day-header ${isToday ? "today" : ""}">${letter}${dt.getDate()}</div>`;
    }

    // 3 rows: apertura / entrega / cierre
    const forms = [
        { key: "apertura", label: "Apert." },
        { key: "entrega",  label: "Entrega" },
        { key: "cierre",   label: "Cierre" },
    ];
    for (const f of forms) {
        html += `<div class="heat-label">${f.label}</div>`;
        for (const d of sortedDays) {
            const e = byDayForm[`${d}__${f.key}`];
            const isFuture = new Date(d + "T00:00:00") > new Date(today + "T00:00:00");
            if (isFuture) {
                html += `<div class="heat-cell heat-future"></div>`;
                continue;
            }
            if (!e || e.n === 0) {
                html += `<div class="heat-cell heat-empty">—</div>`;
                continue;
            }
            const pct = (e.sum / e.n) * 100;
            html += `<div class="heat-cell ${heatClass(pct)}" title="${d} ${f.key}: ${pct.toFixed(0)}%">${pct.toFixed(0)}</div>`;
        }
    }
    grid.innerHTML = html;
}

// ---------------- Ranking ----------------
async function loadRanking() {
    const data = await api(`/ranking?scope=${state.rankingScope}&periodo=${getPeriodoQuery()}`);
    const list = document.getElementById("ranking-list");
    list.innerHTML = "";
    const items = data.items.slice(0, 10);
    for (const item of items) {
        const meta = state.rankingScope === "go"
            ? `${item.n_sucursales} sucs · ${item.n_on_time + item.n_late} de ${item.n_total} ✓`
            : (item.go_nombre || "");
        const row = document.createElement("div");
        row.className = "ranking-item";
        row.innerHTML = `
            <span class="ranking-rank">${item.rank}</span>
            <div>
                <div class="ranking-name">${escapeHtml(item.nombre || "—")}</div>
                <div class="ranking-meta">${escapeHtml(meta)}</div>
            </div>
            <div class="ranking-score">
                <span class="ranking-pct ${pctClass(item.pct_compliance)}">${item.pct_compliance.toFixed(1)}</span>
            </div>
        `;
        row.addEventListener("click", () => openDrillDown(state.rankingScope, item.id, item.nombre));
        list.appendChild(row);
    }
    document.getElementById("ranking-toggle").textContent =
        state.rankingScope === "go" ? "Ver sucursales →" : "← Ver grupos";
}

document.getElementById("ranking-toggle").addEventListener("click", () => {
    state.rankingScope = state.rankingScope === "go" ? "sucursal" : "go";
    loadRanking();
});

// ---------------- Drill-down modal ----------------
async function openDrillDown(scope, id, nombre) {
    showModal(`<h2 class="modal-title">${escapeHtml(nombre || "")}</h2><p class="kpi-sublabel" style="margin-top:8px">Cargando…</p>`);
    try {
        const path = scope === "go" ? `/grupo/${id}` : `/sucursal/${id}`;
        const data = await api(`${path}?periodo=${getPeriodoQuery()}`);
        document.getElementById("modal-content").innerHTML = scope === "go"
            ? renderGrupoDetail(data)
            : renderSucursalDetail(data);
        // Click en sucursal del modal de GO → abre sucursal
        document.querySelectorAll("[data-suc-id]").forEach(el => {
            el.addEventListener("click", () => {
                openDrillDown("sucursal", parseInt(el.dataset.sucId, 10), el.dataset.sucName);
            });
        });
    } catch (e) {
        document.getElementById("modal-content").innerHTML =
            `<p style="color:var(--critical)">Error: ${escapeHtml(e.message)}</p>`;
    }
}

function renderGrupoDetail(d) {
    const o = d.overall;
    const sucs = d.sucursales.map(s => `
        <div class="suc-item" data-suc-id="${s.location_id}" data-suc-name="${escapeHtml(s.nombre)}">
            <div>
                <div class="suc-name">${escapeHtml(s.nombre)}</div>
                <div class="suc-meta">${s.n_on_time} ✓ · ${s.n_late} ↺ · ${s.n_missed} ✗</div>
            </div>
            <span class="suc-pct ${pctClass(s.pct_compliance)}">${s.pct_compliance.toFixed(1)}%</span>
        </div>
    `).join("");
    return `
        <div class="crumb-bar">
            <button class="back-btn" onclick="closeModal()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <div>
                <div class="modal-title">${escapeHtml(d.grupo.nombre)}</div>
                <div class="crumb">${d.start} → ${d.end} · ${d.sucursales.length} sucursales</div>
            </div>
        </div>
        <div class="hero-card">
            <div class="hero-grid">
                <div>
                    <div class="hero-value">${o.pct_compliance.toFixed(1)}%</div>
                    <div class="hero-label">Cumplimiento</div>
                </div>
                <div class="hero-meta">
                    ${o.n_on_time} on-time<br>
                    ${o.n_late} tardío<br>
                    ${o.n_missed} faltado
                </div>
            </div>
        </div>
        <div class="stats-row">
            <div class="stat-card"><div class="stat-label">On-time</div><div class="stat-value pct-excellent">${o.n_on_time}</div></div>
            <div class="stat-card"><div class="stat-label">Tardío</div><div class="stat-value pct-regular">${o.n_late}</div></div>
            <div class="stat-card"><div class="stat-label">Faltado</div><div class="stat-value pct-critical">${o.n_missed}</div></div>
        </div>
        <h3 class="section-title">Sucursales</h3>
        <div style="background:var(--bg-card);border-radius:var(--radius);padding:4px 12px">
            ${sucs}
        </div>
    `;
}

function renderSucursalDetail(d) {
    const days = d.days.map(day => {
        const cells = ["apertura","entrega","cierre"].map(fk => {
            const f = day.forms[fk];
            if (!f) return `<td class="heat-cell heat-empty">—</td>`;
            const pct = f.score * 100;
            return `<td class="heat-cell ${heatClass(pct)}" title="${fk}: ${f.status}">${pct.toFixed(0)}</td>`;
        }).join("");
        return `<tr><th style="font-size:10px;color:var(--text-secondary);padding-right:8px;text-align:left;font-weight:500">${day.day.slice(5)}</th>${cells}<td style="padding-left:8px;font-weight:600;font-size:11px">${day.pct_day.toFixed(0)}%</td></tr>`;
    }).join("");
    const totalDays = d.days.length;
    const avgPct = totalDays ? d.days.reduce((a,b) => a+b.pct_day, 0) / totalDays : 0;
    return `
        <div class="crumb-bar">
            <button class="back-btn" onclick="closeModal()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <div>
                <div class="modal-title">${escapeHtml(d.sucursal.nombre)}</div>
                <div class="crumb">${escapeHtml(d.sucursal.go_nombre || "")} · ${d.start} → ${d.end}</div>
            </div>
        </div>
        <div class="hero-card">
            <div class="hero-grid">
                <div>
                    <div class="hero-value">${avgPct.toFixed(1)}%</div>
                    <div class="hero-label">Promedio del periodo</div>
                </div>
                <div class="hero-meta">${totalDays} día(s)</div>
            </div>
        </div>
        <h3 class="section-title">Por día</h3>
        <div style="background:var(--bg-card);border-radius:var(--radius);padding:12px">
            <table style="width:100%;border-collapse:separate;border-spacing:4px">
                <thead><tr>
                    <th></th>
                    <th style="font-size:9px;color:var(--text-secondary);text-align:center">APE</th>
                    <th style="font-size:9px;color:var(--text-secondary);text-align:center">ENT</th>
                    <th style="font-size:9px;color:var(--text-secondary);text-align:center">CIE</th>
                    <th style="font-size:9px;color:var(--text-secondary);text-align:center">DÍA</th>
                </tr></thead>
                <tbody>${days}</tbody>
            </table>
        </div>
    `;
}

async function openHistoricoModal() {
    showModal(`<h2 class="modal-title">Histórico semanal</h2><p class="kpi-sublabel" style="margin-top:8px">Cargando…</p>`);
    try {
        const data = await api(`/historico?scope=global&semanas=12&form_key=overall`);
        const items = data.items;
        const max = 100;
        const bars = items.map(i => {
            const cls = pctClass(i.pct_compliance);
            return `
                <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0">
                    <div style="font-size:10px;font-weight:700" class="${cls}">${i.pct_compliance.toFixed(0)}</div>
                    <div style="width:100%;background:rgba(255,255,255,0.06);border-radius:4px;height:80px;display:flex;align-items:flex-end">
                        <div style="width:100%;height:${(i.pct_compliance/max)*100}%;border-radius:4px;background:linear-gradient(135deg,var(--accent),var(--accent-light));min-height:3px"></div>
                    </div>
                    <div style="font-size:8px;color:var(--text-secondary)">${i.week_start.slice(5)}</div>
                </div>`;
        }).join("");
        const rows = items.slice().reverse().map(i => {
            const delta = i.delta_prev_week;
            const deltaTxt = delta == null ? "—"
                : `<span class="${delta >= 0 ? "delta-up" : "delta-down"}">${delta >= 0 ? "+" : ""}${delta.toFixed(1)}</span>`;
            return `<tr>
                <td style="padding:8px 4px;font-size:11px;color:var(--text-secondary)">${i.week_start}</td>
                <td style="padding:8px 4px;text-align:right;font-weight:700" class="${pctClass(i.pct_compliance)}">${i.pct_compliance.toFixed(1)}%</td>
                <td style="padding:8px 4px;text-align:right">${deltaTxt}</td>
                <td style="padding:8px 4px;text-align:right;font-size:10px;color:var(--text-secondary)">${i.n_on_time}/${i.n_total}</td>
            </tr>`;
        }).join("");
        document.getElementById("modal-content").innerHTML = `
            <div class="crumb-bar">
                <button class="back-btn" onclick="closeModal()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
                <div>
                    <div class="modal-title">Histórico (12 semanas)</div>
                    <div class="crumb">Cumplimiento global semana a semana</div>
                </div>
            </div>
            <div style="background:var(--bg-card);border-radius:var(--radius);padding:14px;margin-bottom:12px">
                <div style="display:flex;gap:6px;align-items:flex-end">${bars}</div>
            </div>
            <h3 class="section-title">Detalle</h3>
            <table style="width:100%;border-collapse:collapse;background:var(--bg-card);border-radius:var(--radius);overflow:hidden">
                <thead><tr style="font-size:9px;color:var(--text-secondary);text-transform:uppercase">
                    <th style="padding:8px 4px;text-align:left">Semana</th>
                    <th style="padding:8px 4px;text-align:right">Pct</th>
                    <th style="padding:8px 4px;text-align:right">Δ</th>
                    <th style="padding:8px 4px;text-align:right">OT/Total</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    } catch (e) {
        document.getElementById("modal-content").innerHTML =
            `<p style="color:var(--critical)">Error: ${escapeHtml(e.message)}</p>`;
    }
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
window.closeModal = closeModal;

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
});

// ---------------- Bottom nav (alertas modal) ----------------
document.querySelectorAll(".bottom-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        if (tab.dataset.tab === "alertas") openAlertasModal();
        else if (tab.dataset.tab === "hist") openHistoricoModal();
    });
});

async function openAlertasModal() {
    showModal(`<h2 class="modal-title">Alertas</h2><p class="kpi-sublabel" style="margin-top:8px">Cargando…</p>`);
    try {
        const data = await api(`/alertas`);
        const bajo = data.bajo_compliance.length ? data.bajo_compliance.slice(0, 10).map(b => `
            <div class="suc-item">
                <div>
                    <div class="suc-name">${escapeHtml(b.nombre)}</div>
                    <div class="suc-meta">${escapeHtml(b.go_nombre || "")}</div>
                </div>
                <span class="suc-pct pct-critical">${b.pct_compliance.toFixed(1)}%</span>
            </div>`).join("") : `<p style="padding:14px;color:var(--text-secondary);font-size:12px">Sin alertas de bajo cumplimiento.</p>`;
        document.getElementById("modal-content").innerHTML = `
            <div class="crumb-bar">
                <button class="back-btn" onclick="closeModal()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
                <div>
                    <div class="modal-title">Alertas</div>
                    <div class="crumb">Sucursales bajo umbral · pendientes hoy: ${data.pendientes_hoy.length}</div>
                </div>
            </div>
            <h3 class="section-title">Bajo compliance</h3>
            <div style="background:var(--bg-card);border-radius:var(--radius);padding:4px 12px">${bajo}</div>
        `;
    } catch (e) {
        document.getElementById("modal-content").innerHTML =
            `<p style="color:var(--critical)">Error: ${escapeHtml(e.message)}</p>`;
    }
}

// ---------------- Utils ----------------
function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[c]);
}

async function refresh() {
    try {
        await Promise.all([loadPeriod(), loadKpis(), loadHeatmap(), loadRanking()]);
    } catch (e) {
        console.error("refresh error:", e);
    }
}

// ---------------- Init ----------------
initTheme();
initToggle();
refresh();
setInterval(refresh, 60_000);
