// ============================================================
// EPL CAS · Operación Diaria — JS vanilla
// Estructura clonada del dashboard de Supervisiones, adaptada
// a los endpoints /api/operacion/*
// ============================================================
const API = "/api/operacion";

const state = {
    tipo: "week",     // week | month
    offset: 0,        // 0 = actual, -1 = anterior, -2 = dos antes...
    view: "grupos",   // grupos | sucursales
    tab: "dashboard", // dashboard | heatmap | historico | alertas
    currentGoId: null,
};

// =========================================================
// THEME TOGGLE
// =========================================================
function initTheme() {
    const saved = localStorage.getItem("data-theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    document.getElementById("themeToggle").addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        const next = cur === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("data-theme", next);
    });
}

// =========================================================
// API HELPER
// =========================================================
async function api(path) {
    const res = await fetch(API + path);
    if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
    return res.json();
}

// =========================================================
// COLOR HELPERS (mismos thresholds que Supervisiones)
// =========================================================
function pctClass(pct) {
    if (pct >= 90) return "excellent";
    if (pct >= 80) return "good";
    if (pct >= 70) return "regular";
    return "critical";
}
function pctColor(pct) {
    if (pct >= 90) return "var(--excellent)";
    if (pct >= 80) return "var(--good)";
    if (pct >= 70) return "var(--regular)";
    return "var(--critical)";
}

// =========================================================
// MAIN TOGGLE (Semana / Mes)
// =========================================================
function initMainToggle() {
    document.querySelectorAll(".main-toggle .toggle-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".main-toggle .toggle-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.tipo = btn.dataset.tipo;
            state.offset = 0;
            refresh();
        });
    });
}

function getPeriodoQuery() {
    if (state.tipo === "week"  && state.offset === 0)  return "current-week";
    if (state.tipo === "week"  && state.offset === -1) return "prev-week";
    if (state.tipo === "month" && state.offset === 0)  return "current-month";
    return "current-week";
}

// =========================================================
// PERIOD BAR + SHEET PICKER
// =========================================================
function initPeriodSheet() {
    const selector = document.getElementById("periodSelector");
    const overlay = document.getElementById("periodSheetOverlay");
    const body = document.getElementById("periodSheetBody");

    selector.addEventListener("click", async () => {
        selector.classList.add("open");
        // construir opciones según tipo
        const opts = [];
        if (state.tipo === "week") {
            for (let i = 0; i >= -8; i--) {
                const data = await api(`/periodo?tipo=week&offset=${i}`);
                opts.push({ ...data, offset: i });
            }
        } else {
            for (let i = 0; i >= -6; i--) {
                const data = await api(`/periodo?tipo=month&offset=${i}`);
                opts.push({ ...data, offset: i });
            }
        }
        body.innerHTML = opts.map(o => `
            <div class="period-option ${o.offset === state.offset ? "selected" : ""}" data-offset="${o.offset}">
                <div class="period-option-info">
                    <div class="period-option-name">${formatPeriodName(o.tipo, o.start, o.end, o.is_current)}</div>
                    <div class="period-option-dates">${formatDateRange(o.start, o.end)}</div>
                </div>
                <div class="period-option-check">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                </div>
            </div>
        `).join("");
        body.querySelectorAll(".period-option").forEach(el => {
            el.addEventListener("click", () => {
                state.offset = parseInt(el.dataset.offset, 10);
                overlay.classList.remove("active");
                selector.classList.remove("open");
                refresh();
            });
        });
        overlay.classList.add("active");
    });

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
            overlay.classList.remove("active");
            selector.classList.remove("open");
        }
    });
}

function formatPeriodName(tipo, startISO, endISO, isCurrent) {
    if (tipo === "week") {
        return isCurrent ? "Semana actual" : `Semana del ${formatShort(startISO)}`;
    }
    const months = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
    const d = new Date(startISO + "T00:00:00");
    return `${months[d.getMonth()]} ${d.getFullYear()}${isCurrent ? " (actual)" : ""}`;
}
function formatDateRange(s, e) {
    return `${formatShort(s)} — ${formatShort(e)}`;
}
function formatShort(iso) {
    const months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
    const d = new Date(iso + "T00:00:00");
    return `${d.getDate()} ${months[d.getMonth()]}`;
}

async function loadPeriod() {
    const data = await api(`/periodo?tipo=${state.tipo}&offset=${state.offset}`);
    document.getElementById("periodName").textContent =
        formatPeriodName(state.tipo, data.start, data.end, data.is_current);
}

// =========================================================
// KPIs + DISTRIBUTION (por formulario)
// =========================================================
async function loadDashboard() {
    const kpis = await api(`/kpis?periodo=${getPeriodoQuery()}`);
    const o = kpis.overall;

    // Card principal
    const pctEl = document.getElementById("kpiPromedio");
    pctEl.textContent = `${o.pct_compliance.toFixed(1)}%`;
    document.getElementById("kpiTotal").textContent = o.n_total;
    document.getElementById("kpiGrupos").textContent = o.n_on_time;
    document.getElementById("kpiSucursales").textContent = o.n_missed;

    // Progress text in period bar
    document.getElementById("progressText").textContent = `${o.pct_compliance.toFixed(1)}%`;

    // Acumulado: delta vs semana anterior (si hay)
    try {
        const hist = await api(`/historico?scope=global&semanas=2&form_key=overall`);
        const items = hist.items || [];
        const last = items[items.length - 1];
        if (last && last.delta_prev_week != null) {
            const d = last.delta_prev_week;
            const sign = d >= 0 ? "▲ +" : "▼ ";
            document.getElementById("kpiAcumulado").textContent = `${sign}${d.toFixed(1)} pts`;
            document.getElementById("kpiAcumulado").style.color = d >= 0
                ? "rgba(255, 255, 255, 0.95)"
                : "rgba(255, 255, 255, 0.75)";
        } else {
            document.getElementById("kpiAcumulado").textContent = `${o.n_on_time}/${o.n_total} on-time`;
        }
    } catch {
        document.getElementById("kpiAcumulado").textContent = `${o.n_on_time}/${o.n_total} on-time`;
    }

    // Distribution: por formulario (3 barras horizontales)
    const formNames = { apertura: "Apertura · 07-11 h", entrega: "Entrega · 14-17 h", cierre: "Cierre · 19-23 h" };
    const order = ["apertura", "entrega", "cierre"];
    const byKey = Object.fromEntries(kpis.per_form.map(f => [f.form_key, f]));
    const bars = order.map(key => {
        const f = byKey[key];
        if (!f) return "";
        const pct = f.pct_compliance;
        const cls = pctClass(pct);
        return `
            <div class="distribution-bar">
                <div class="distribution-bar-label">
                    <span>${formNames[key]}</span>
                    <span class="distribution-bar-value bar-${cls}">${pct.toFixed(1)}%</span>
                </div>
                <div class="distribution-bar-track">
                    <div class="distribution-bar-fill bar-${cls}" style="width: ${pct}%"></div>
                </div>
                <div class="distribution-bar-meta">
                    ${f.n_on_time} a tiempo · ${f.n_late} tardío · ${f.n_missed} faltado
                </div>
            </div>
        `;
    }).join("");
    document.getElementById("distributionBars").innerHTML = bars;
}

// =========================================================
// RANKING (GO o Sucursal)
// =========================================================
function initSecondaryToggles() {
    document.querySelectorAll(".secondary-toggles .sub-toggle").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".secondary-toggles .sub-toggle").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.view = btn.dataset.view;
            document.getElementById("rankingTitle").textContent =
                state.view === "grupos" ? "de Grupos" : "de Sucursales";
            loadRanking();
        });
    });
}

async function loadRanking() {
    const scope = state.view === "grupos" ? "go" : "sucursal";
    const data = await api(`/ranking?scope=${scope}&periodo=${getPeriodoQuery()}`);
    // Mostrar TODOS los items del catálogo (no truncar) — incluye los que tienen 0%
    const items = data.items;
    const html = items.map(item => {
        const cls = item.sin_data ? "critical" : pctClass(item.pct_compliance);
        const meta = scope === "go"
            ? (item.sin_data
                ? `${item.n_sucursales} sucursales · sin evaluaciones en periodo`
                : `${item.n_sucursales} sucursales · ${item.n_on_time}/${item.n_total} a tiempo`)
            : (item.sin_data
                ? `${item.go_nombre || ""} · sin evaluaciones`
                : `${item.go_nombre || ""} · ${item.n_on_time}/${item.n_total} a tiempo`);
        const pctText = item.sin_data ? "—" : `${item.pct_compliance.toFixed(1)}%`;
        return `
            <div class="ranking-item ${item.sin_data ? "sin-data" : ""}" data-id="${item.id}" data-scope="${scope}" data-name="${escapeHtml(item.nombre || "")}">
                <div class="ranking-rank">${item.rank}</div>
                <div class="ranking-info">
                    <div class="ranking-name">${escapeHtml(item.nombre || "—")}</div>
                    <div class="ranking-meta">${escapeHtml(meta)}</div>
                </div>
                <div class="ranking-score">
                    <span class="ranking-pct pct-${cls}">${pctText}</span>
                </div>
            </div>
        `;
    }).join("");
    const list = document.getElementById("rankingList");
    list.innerHTML = html || `<div class="loading">Sin datos en este periodo.</div>`;

    list.querySelectorAll(".ranking-item").forEach(el => {
        el.addEventListener("click", () => {
            openDrillDown(el.dataset.scope, parseInt(el.dataset.id, 10), el.dataset.name);
        });
    });
}

// =========================================================
// DRILL-DOWN MODALS (GO / Sucursal)
// =========================================================
function initModals() {
    document.getElementById("modalClose").addEventListener("click", () => closeModal("modalOverlay"));
    document.getElementById("modalOverlay").addEventListener("click", (e) => {
        if (e.target.id === "modalOverlay") closeModal("modalOverlay");
    });
    document.getElementById("sucursalModalClose").addEventListener("click", () => closeModal("sucursalModalOverlay"));
    document.getElementById("sucursalModalOverlay").addEventListener("click", (e) => {
        if (e.target.id === "sucursalModalOverlay") closeModal("sucursalModalOverlay");
    });
    document.getElementById("modalBack").addEventListener("click", () => {
        closeModal("sucursalModalOverlay");
    });
}

function openModal(id) {
    document.getElementById(id).classList.add("active");
    document.body.classList.add("scroll-locked");
}
function closeModal(id) {
    document.getElementById(id).classList.remove("active");
    if (id === "modalOverlay") {
        document.body.classList.remove("scroll-locked");
    } else if (!document.getElementById("modalOverlay").classList.contains("active")) {
        document.body.classList.remove("scroll-locked");
    }
}

async function openDrillDown(scope, id, nombre) {
    if (scope === "go") {
        state.currentGoId = id;
        document.getElementById("modalTitle").textContent = nombre || "Grupo";
        document.getElementById("modalBody").innerHTML = `<div class="loading">Cargando...</div>`;
        openModal("modalOverlay");
        try {
            const data = await api(`/grupo/${id}?periodo=${getPeriodoQuery()}`);
            document.getElementById("modalBody").innerHTML = renderGrupoDetail(data);
            document.querySelectorAll("#modalBody [data-suc-id]").forEach(el => {
                el.addEventListener("click", () => {
                    openDrillDown("sucursal", parseInt(el.dataset.sucId, 10), el.dataset.sucName);
                });
            });
        } catch (e) {
            document.getElementById("modalBody").innerHTML = `<p style="color:var(--critical);padding:16px">${escapeHtml(e.message)}</p>`;
        }
    } else {
        document.getElementById("sucursalModalTitle").textContent = nombre || "Sucursal";
        document.getElementById("sucursalModalBody").innerHTML = `<div class="loading">Cargando...</div>`;
        openModal("sucursalModalOverlay");
        try {
            // Pedir 28 días para calendar completo
            const data = await api(`/sucursal/${id}?dias=28`);
            document.getElementById("sucursalModalBody").innerHTML = renderSucursalDetail(data);
        } catch (e) {
            document.getElementById("sucursalModalBody").innerHTML = `<p style="color:var(--critical);padding:16px">${escapeHtml(e.message)}</p>`;
        }
    }
}

function renderGrupoDetail(d) {
    const o = d.overall;
    const cls = pctClass(o.pct_compliance);
    const sucs = d.sucursales.map(s => {
        const sc = pctClass(s.pct_compliance);
        return `
            <div class="ranking-item" data-suc-id="${s.location_id}" data-suc-name="${escapeHtml(s.nombre)}">
                <div class="ranking-rank">·</div>
                <div class="ranking-info">
                    <div class="ranking-name">${escapeHtml(s.nombre)}</div>
                    <div class="ranking-meta">${s.n_on_time}/${s.n_total} · ${s.n_late} tardío · ${s.n_missed} faltado</div>
                </div>
                <div class="ranking-score">
                    <span class="ranking-pct pct-${sc}">${s.pct_compliance.toFixed(1)}%</span>
                </div>
            </div>
        `;
    }).join("");
    return `
        <div class="modal-summary">
            <div class="modal-summary-card main">
                <span class="modal-summary-value">${o.pct_compliance.toFixed(1)}%</span>
                <span class="modal-summary-label">Cumplimiento</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value">${o.n_on_time}</span>
                <span class="modal-summary-label">A tiempo</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value">${o.n_late}</span>
                <span class="modal-summary-label">Tardío</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value">${o.n_missed}</span>
                <span class="modal-summary-label">Faltado</span>
            </div>
        </div>
        <h3 class="section-title">Sucursales (${d.sucursales.length})</h3>
        <div class="ranking-list">${sucs}</div>
    `;
}

function renderSucursalDetail(d) {
    const totalDays = d.days.length;
    const avgPct = totalDays ? d.days.reduce((a,b) => a + b.pct_day, 0) / totalDays : 0;
    const formLabels = { apertura: "Apertura", entrega: "Entrega", cierre: "Cierre" };
    const formTimes  = { apertura: "07-11 h", entrega: "14-17 h", cierre: "19-23 h" };

    // Stats 3 col (% por formulario en el periodo completo)
    const formStats = {};
    for (const fk of ["apertura","entrega","cierre"]) {
        let on = 0, late = 0, missed = 0;
        for (const day of d.days) {
            const f = day.forms[fk];
            if (!f) { missed++; continue; }
            if (f.status === "on_time") on++;
            else if (f.status === "late") late++;
            else missed++;
        }
        const total = on + late + missed;
        const pct = total ? ((on * 100 + late * 50) / total) : 0;
        formStats[fk] = { on, late, missed, pct };
    }

    // Calendar 28 días en filas de 7 (semanas)
    const dayByDate = Object.fromEntries(d.days.map(x => [x.day, x]));
    const today = new Date().toISOString().slice(0, 10);
    const startDate = new Date(d.start + "T00:00:00");
    const endDate = new Date(d.end + "T00:00:00");
    // Alinear inicio a lunes
    let cursor = new Date(startDate);
    const dow = cursor.getDay(); // 0=dom
    const lunesOffset = dow === 0 ? -6 : 1 - dow;
    cursor.setDate(cursor.getDate() + lunesOffset);
    const weeks = [];
    while (cursor <= endDate || weeks.length === 0 || cursor.getDay() !== 1) {
        const week = [];
        for (let i = 0; i < 7; i++) {
            const iso = cursor.toISOString().slice(0, 10);
            week.push({ iso, date: new Date(cursor) });
            cursor.setDate(cursor.getDate() + 1);
        }
        weeks.push(week);
        if (cursor > endDate && cursor.getDay() === 1) break;
        if (weeks.length >= 5) break;
    }

    const weekRows = weeks.map((week, idx) => {
        const cells = week.map(cell => {
            const isFuture = cell.iso > today;
            if (isFuture) return `<div class="cal-cell cell-future"><span class="cell-day">${cell.date.getDate()}</span></div>`;
            const day = dayByDate[cell.iso];
            if (!day) return `<div class="cal-cell cell-empty"><span class="cell-day">${cell.date.getDate()}</span></div>`;
            const pct = day.pct_day;
            const cls = pct >= 90 ? "cell-excellent" : pct >= 70 ? "cell-good" : pct >= 50 ? "cell-regular" : "cell-critical";
            const todayCls = cell.iso === today ? " cell-today" : "";
            return `<div class="cal-cell ${cls}${todayCls}"><span class="cell-day">${cell.date.getDate()}</span><span class="cell-score">${pct.toFixed(0)}</span></div>`;
        }).join("");
        return `<div class="cal-row"><span class="cal-week-label">S${idx+1}</span>${cells}</div>`;
    }).join("");

    // Submission list de HOY
    const todayData = dayByDate[today];
    let submissionList = `<p style="padding:16px;color:var(--text-secondary);text-align:center">Sin datos de hoy.</p>`;
    if (todayData) {
        const items = ["apertura", "entrega", "cierre"].map(fk => {
            const f = todayData.forms[fk];
            if (!f) {
                return `
                    <div class="sub-item">
                        <span class="sub-time">—</span>
                        <div>
                            <div class="sub-name">${formLabels[fk]}</div>
                            <div class="sub-meta">Pendiente · ventana ${formTimes[fk]}</div>
                        </div>
                        <span class="badge badge-pending">pendiente</span>
                    </div>`;
            }
            const dt = f.completed_at ? new Date(f.completed_at) : null;
            // Hora local Monterrey (UTC-6)
            const hh = dt ? String(dt.getUTCHours() - 6 < 0 ? 24 + dt.getUTCHours() - 6 : dt.getUTCHours() - 6).padStart(2, "0") : "—";
            const mm = dt ? String(dt.getUTCMinutes()).padStart(2, "0") : "—";
            const horaLocal = dt ? `${hh}:${mm}` : "—";
            const badgeCls = f.status === "on_time" ? "badge-ontime"
                          : f.status === "late" ? "badge-late"
                          : "badge-missed";
            const badgeText = f.status === "on_time" ? "a tiempo"
                          : f.status === "late" ? "tardío"
                          : "faltó";
            const metaText = f.status === "on_time"
                ? `Entregado dentro de ventana (${formTimes[fk]})`
                : f.status === "late"
                ? `Fuera de ventana ${formTimes[fk]}`
                : `Sin envío · ventana ${formTimes[fk]}`;
            return `
                <div class="sub-item">
                    <span class="sub-time">${horaLocal}</span>
                    <div>
                        <div class="sub-name">${formLabels[fk]}</div>
                        <div class="sub-meta">${metaText}</div>
                    </div>
                    <span class="badge ${badgeCls}">${badgeText}</span>
                </div>`;
        }).join("");
        submissionList = `<div class="submission-list">${items}</div>`;
    }

    return `
        <div class="modal-summary">
            <div class="modal-summary-card main">
                <span class="modal-summary-value">${avgPct.toFixed(1)}%</span>
                <span class="modal-summary-label">Cumplimiento ${totalDays}d</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value pct-${pctClass(formStats.apertura.pct)}">${formStats.apertura.pct.toFixed(0)}</span>
                <span class="modal-summary-label">Apertura<br>07-11h</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value pct-${pctClass(formStats.entrega.pct)}">${formStats.entrega.pct.toFixed(0)}</span>
                <span class="modal-summary-label">Entrega<br>14-17h</span>
            </div>
            <div class="modal-summary-card">
                <span class="modal-summary-value pct-${pctClass(formStats.cierre.pct)}">${formStats.cierre.pct.toFixed(0)}</span>
                <span class="modal-summary-label">Cierre<br>19-23h</span>
            </div>
        </div>

        <h3 class="section-title">Calendario · últimos 28 días</h3>
        <div class="calendar">
            <div class="cal-header">
                <span></span>
                <div class="cal-day-label">L</div><div class="cal-day-label">M</div><div class="cal-day-label">X</div>
                <div class="cal-day-label">J</div><div class="cal-day-label">V</div><div class="cal-day-label">S</div><div class="cal-day-label">D</div>
            </div>
            ${weekRows}
            <div class="legend" style="margin-top:12px">
                <span><span class="legend-dot" style="background:var(--excellent)"></span>≥90</span>
                <span><span class="legend-dot" style="background:var(--good)"></span>70-89</span>
                <span><span class="legend-dot" style="background:var(--regular)"></span>50-69</span>
                <span><span class="legend-dot" style="background:var(--critical)"></span>&lt;50</span>
            </div>
        </div>

        <h3 class="section-title">Hoy · ${new Date().toLocaleDateString("es-MX", {weekday:"long", day:"numeric", month:"long"})}</h3>
        ${submissionList}
    `;
}

// =========================================================
// HEATMAP TAB (3 forms × 7 days)
// =========================================================
async function loadHeatmap() {
    try {
        const data = await api(`/heatmap?periodo=${getPeriodoQuery()}`);
        const byDayForm = {};
        const days = new Set();
        for (const c of data.cells) {
            if (!c.day) continue;
            days.add(c.day);
            const k = `${c.day}__${c.form_key}`;
            if (!byDayForm[k]) byDayForm[k] = { sum: 0, n: 0 };
            if (c.score != null) { byDayForm[k].sum += c.score; byDayForm[k].n++; }
            else if (c.status === "missed") { byDayForm[k].n++; }
        }
        const sortedDays = Array.from(days).sort();
        const today = new Date().toISOString().slice(0, 10);
        const dayLetters = ["D","L","M","X","J","V","S"];

        let header = `<th></th>`;
        for (const d of sortedDays) {
            const dt = new Date(d + "T00:00:00");
            const cls = d === today ? "today" : "";
            header += `<th class="${cls}">${dayLetters[dt.getDay()]}<br><small>${dt.getDate()}</small></th>`;
        }
        const forms = [
            { key: "apertura", label: "Apertura", time: "07-11 h" },
            { key: "entrega",  label: "Entrega",  time: "14-17 h" },
            { key: "cierre",   label: "Cierre",   time: "19-23 h" },
        ];
        const rows = forms.map(f => {
            const cells = sortedDays.map(d => {
                const e = byDayForm[`${d}__${f.key}`];
                const isFuture = d > today;
                if (isFuture) return `<td class="heat-cell-big heat-future-big"></td>`;
                if (!e || e.n === 0) return `<td class="heat-cell-big heat-empty-big">—</td>`;
                const pct = (e.sum / e.n) * 100;
                const cls = pctClass(pct);
                return `<td class="heat-cell-big heat-${cls}-big" title="${d}: ${pct.toFixed(0)}%">${pct.toFixed(0)}</td>`;
            }).join("");
            return `
                <tr>
                    <td class="heat-row-label">
                        <strong>${f.label}</strong><br>
                        <small>${f.time}</small>
                    </td>
                    ${cells}
                </tr>`;
        }).join("");
        document.getElementById("heatmapContainer").innerHTML = `
            <table class="heatmap-table">
                <thead><tr>${header}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
            <div class="heatmap-legend">
                <div class="legend-item"><span class="dot excellent"></span>Excelente (≥90%)</div>
                <div class="legend-item"><span class="dot good"></span>Bueno (80-89%)</div>
                <div class="legend-item"><span class="dot regular"></span>Regular (70-79%)</div>
                <div class="legend-item"><span class="dot critical"></span>Crítico (&lt;70%)</div>
            </div>
        `;
    } catch (e) {
        document.getElementById("heatmapContainer").innerHTML =
            `<p style="color:var(--critical);padding:16px">${escapeHtml(e.message)}</p>`;
    }
}

// =========================================================
// HISTORICO TAB
// =========================================================
async function loadHistorico() {
    try {
        const data = await api(`/historico?scope=global&semanas=12&form_key=overall`);
        const items = data.items;
        if (!items.length) {
            document.getElementById("historicoContainer").innerHTML = `<div class="loading">Sin datos históricos.</div>`;
            return;
        }
        const maxPct = 100;
        const bars = items.map(i => {
            const cls = pctClass(i.pct_compliance);
            const h = Math.max((i.pct_compliance / maxPct) * 100, 3);
            return `
                <div class="hist-bar-col">
                    <div class="hist-bar-value pct-${cls}">${i.pct_compliance.toFixed(0)}</div>
                    <div class="hist-bar-track">
                        <div class="hist-bar-fill bar-${cls}" style="height:${h}%"></div>
                    </div>
                    <div class="hist-bar-label">${i.week_start.slice(5)}</div>
                </div>`;
        }).join("");
        const rows = items.slice().reverse().map(i => {
            const cls = pctClass(i.pct_compliance);
            const d = i.delta_prev_week;
            const deltaHtml = d == null
                ? `<span style="color:var(--text-secondary)">—</span>`
                : `<span style="color:${d >= 0 ? "var(--excellent)" : "var(--critical)"};font-weight:600">${d >= 0 ? "▲ +" : "▼ "}${d.toFixed(1)}</span>`;
            return `
                <tr>
                    <td>${i.week_start}</td>
                    <td><span class="pct-${cls}" style="font-weight:700">${i.pct_compliance.toFixed(1)}%</span></td>
                    <td>${deltaHtml}</td>
                    <td>${i.n_on_time}/${i.n_total}</td>
                </tr>`;
        }).join("");
        document.getElementById("historicoContainer").innerHTML = `
            <div class="hist-chart">${bars}</div>
            <h3 class="section-title" style="margin-top:24px">Detalle</h3>
            <table class="hist-table">
                <thead><tr><th>Semana</th><th>Cumpl.</th><th>Δ</th><th>OT/Total</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    } catch (e) {
        document.getElementById("historicoContainer").innerHTML =
            `<p style="color:var(--critical);padding:16px">${escapeHtml(e.message)}</p>`;
    }
}

// =========================================================
// ALERTAS TAB
// =========================================================
async function loadAlertas() {
    try {
        const data = await api(`/alertas`);
        const renderList = (items, emptyMsg) => {
            if (!items.length) return `<div class="loading">${emptyMsg}</div>`;
            return items.slice(0, 20).map(b => {
                const cls = pctClass(b.pct_compliance != null ? b.pct_compliance : 0);
                return `
                    <div class="ranking-item">
                        <div class="ranking-rank">·</div>
                        <div class="ranking-info">
                            <div class="ranking-name">${escapeHtml(b.nombre)}</div>
                            <div class="ranking-meta">${escapeHtml(b.go_nombre || "")}${b.form_key ? " · " + escapeHtml(b.form_key) : ""}</div>
                        </div>
                        <div class="ranking-score">
                            ${b.pct_compliance != null
                                ? `<span class="ranking-pct pct-${cls}">${b.pct_compliance.toFixed(1)}%</span>`
                                : `<span class="ranking-pct pct-critical">pendiente</span>`}
                        </div>
                    </div>`;
            }).join("");
        };
        const criticos = data.bajo_compliance.filter(b => b.pct_compliance < 70);
        const warnings = data.bajo_compliance.filter(b => b.pct_compliance >= 70 && b.pct_compliance < 80);

        document.getElementById("alertasCriticos").innerHTML =
            renderList(criticos, "Sin alertas críticas.");
        document.getElementById("alertasWarning").innerHTML =
            renderList(warnings, "Sin sucursales en riesgo.");
        document.getElementById("alertasPendientes").innerHTML =
            renderList(data.pendientes_hoy, "Todas las sucursales completaron hoy.");

        document.getElementById("alertasSummary").innerHTML = `
            <div class="alertas-summary-card critical">
                <div class="alertas-summary-value">${criticos.length}</div>
                <div class="alertas-summary-label">Críticos</div>
            </div>
            <div class="alertas-summary-card warning">
                <div class="alertas-summary-value">${warnings.length}</div>
                <div class="alertas-summary-label">En riesgo</div>
            </div>
            <div class="alertas-summary-card">
                <div class="alertas-summary-value">${data.pendientes_hoy.length}</div>
                <div class="alertas-summary-label">Pendientes hoy</div>
            </div>
        `;
    } catch (e) {
        document.getElementById("alertasCriticos").innerHTML =
            `<p style="color:var(--critical);padding:16px">${escapeHtml(e.message)}</p>`;
    }
}

// =========================================================
// BOTTOM NAV (tab switching)
// =========================================================
function initBottomNav() {
    document.querySelectorAll(".bottom-nav .bottom-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            document.querySelectorAll(".bottom-nav .bottom-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
            document.getElementById(target).classList.add("active");
            state.tab = target;
            window.scrollTo(0, 0);
            loadCurrentTab();
        });
    });
}

function loadCurrentTab() {
    if (state.tab === "dashboard") { loadDashboard(); loadRanking(); }
    else if (state.tab === "heatmap")   loadHeatmap();
    else if (state.tab === "historico") loadHistorico();
    else if (state.tab === "alertas")   loadAlertas();
}

// =========================================================
// UTILS
// =========================================================
function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[c]);
}

async function refresh() {
    try {
        await loadPeriod();
        await loadCurrentTab();
    } catch (e) {
        console.error("refresh error:", e);
    }
}

// =========================================================
// INIT
// =========================================================
initTheme();
initMainToggle();
initPeriodSheet();
initSecondaryToggles();
initBottomNav();
initModals();
refresh();
setInterval(refresh, 90_000);
