/**
 * EPL CAS 2026 - Dashboard Application
 * Complete JavaScript with all functionality
 */

// State
let currentTipo = 'operativas';
let currentView = 'grupos';
let currentTerritorio = 'todas';
let currentHistView = 'grupos';
let map = null;
let markers = [];
let currentGrupoId = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initToggles();
    initTabs();
    initModals();
    loadDashboard();
});

// ========== TOGGLES ==========
function initToggles() {
    // Main toggle: Operativas / Seguridad
    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTipo = btn.dataset.tipo;
            loadDashboard();
        });
    });

    // Sub toggle: Grupos / Sucursales
    document.querySelectorAll('.sub-toggle[data-view]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sub-toggle[data-view]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentView = btn.dataset.view;
            document.getElementById('rankingTitle').textContent =
                currentView === 'grupos' ? 'de Grupos' : 'de Sucursales';
            loadRanking();
        });
    });

    // Territorio toggle
    document.querySelectorAll('.territorio-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.territorio-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTerritorio = btn.dataset.territorio;
            loadRanking();
        });
    });

    // Historico toggle
    document.querySelectorAll('.sub-toggle[data-hist]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sub-toggle[data-hist]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentHistView = btn.dataset.hist;
            loadHistorico();
        });
    });
}

// ========== TABS ==========
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            document.getElementById(tabId).classList.add('active');

            // Load tab-specific data
            if (tabId === 'mapa') {
                initMap();
                loadMapData();
            } else if (tabId === 'historico') {
                loadHistorico();
            } else if (tabId === 'alertas') {
                loadAlertas();
            }
        });
    });
}

// ========== MODALS ==========
function initModals() {
    // Group detail modal
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modalOverlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('modalOverlay')) closeModal();
    });

    // Sucursal detail modal
    document.getElementById('sucursalModalClose').addEventListener('click', closeSucursalModal);
    document.getElementById('modalBack').addEventListener('click', () => {
        closeSucursalModal();
        if (currentGrupoId) openGrupoModal(currentGrupoId);
    });
    document.getElementById('sucursalModalOverlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('sucursalModalOverlay')) closeSucursalModal();
    });
}

function openModal() {
    document.getElementById('modalOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('modalOverlay').classList.remove('active');
    document.body.style.overflow = '';
}

function openSucursalModal() {
    document.getElementById('sucursalModalOverlay').classList.add('active');
}

function closeSucursalModal() {
    document.getElementById('sucursalModalOverlay').classList.remove('active');
}

// ========== LOAD DASHBOARD ==========
function loadDashboard() {
    loadKPIs();
    loadRanking();
}

// ========== KPIs ==========
async function loadKPIs() {
    try {
        const res = await fetch(`/api/kpis/${currentTipo}`);
        const data = await res.json();
        if (data.success) {
            const d = data.data;
            document.getElementById('kpiPromedio').textContent = d.promedio || '-';
            document.getElementById('kpiPromedio').className = `kpi-value ${d.color || 'gray'}`;
            document.getElementById('kpiTotal').textContent = d.total_supervisiones || 0;
            document.getElementById('kpiGrupos').textContent = d.total_grupos || 0;
            document.getElementById('kpiSucursales').textContent = d.sucursales_supervisadas || 0;

            // Distribution bars
            renderDistribution(d.distribucion || {});
        }
    } catch (e) {
        console.error('Error loading KPIs:', e);
    }
}

function renderDistribution(dist) {
    const container = document.getElementById('distributionBars');
    const total = (dist.excelente || 0) + (dist.bueno || 0) + (dist.regular || 0) + (dist.critico || 0);

    if (total === 0) {
        container.innerHTML = '<div class="empty-state">Sin datos</div>';
        return;
    }

    const items = [
        { label: 'Excelente', count: dist.excelente || 0, class: 'excellent' },
        { label: 'Bueno', count: dist.bueno || 0, class: 'good' },
        { label: 'Regular', count: dist.regular || 0, class: 'regular' },
        { label: 'Critico', count: dist.critico || 0, class: 'critical' }
    ];

    container.innerHTML = items.map(item => {
        const pct = ((item.count / total) * 100).toFixed(0);
        return `
            <div class="dist-bar">
                <div class="dist-label">
                    <span class="dist-name ${item.class}">${item.label}</span>
                    <span class="dist-count">${item.count} (${pct}%)</span>
                </div>
                <div class="dist-track">
                    <div class="dist-fill ${item.class}" style="width: ${pct}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// ========== RANKING ==========
async function loadRanking() {
    const container = document.getElementById('rankingList');
    container.innerHTML = '<div class="loading">Cargando...</div>';

    try {
        const endpoint = currentView === 'grupos'
            ? `/api/ranking/grupos/${currentTipo}`
            : `/api/ranking/sucursales/${currentTipo}`;

        const res = await fetch(endpoint);
        const data = await res.json();

        if (data.success && data.data.length > 0) {
            let items = data.data;

            // Filter by territorio if not "todas"
            if (currentTerritorio !== 'todas' && currentView === 'grupos') {
                items = items.filter(item => item.territorio === currentTerritorio);
            }

            if (items.length === 0) {
                container.innerHTML = '<div class="empty-state">Sin resultados para este filtro</div>';
                return;
            }

            container.innerHTML = items.map((item, i) => {
                const calificacion = item.promedio;
                const colorClass = item.color || getColorClass(calificacion);

                if (currentView === 'grupos') {
                    return `
                        <div class="ranking-item" onclick="openGrupoModal(${item.id})">
                            <span class="ranking-pos pos-${i + 1}">${i + 1}</span>
                            <div class="ranking-info">
                                <span class="ranking-name">${item.nombre}</span>
                                <span class="ranking-meta">${item.total_sucursales} sucursales | ${item.territorio}</span>
                            </div>
                            <span class="ranking-score ${colorClass}">${calificacion}</span>
                        </div>
                    `;
                } else {
                    return `
                        <div class="ranking-item" onclick="openSucursalDetailModal(${item.id})">
                            <span class="ranking-pos pos-${i + 1}">${i + 1}</span>
                            <div class="ranking-info">
                                <span class="ranking-name">${item.nombre}</span>
                                <span class="ranking-meta">${item.grupo_nombre || '-'}</span>
                            </div>
                            <span class="ranking-score ${colorClass}">${calificacion}</span>
                        </div>
                    `;
                }
            }).join('');
        } else {
            container.innerHTML = '<div class="empty-state">No hay datos de ranking</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar ranking</div>';
    }
}

// ========== GRUPO MODAL ==========
async function openGrupoModal(grupoId) {
    currentGrupoId = grupoId;
    const modalBody = document.getElementById('modalBody');
    modalBody.innerHTML = '<div class="loading">Cargando...</div>';
    openModal();

    try {
        const res = await fetch(`/api/grupo/${grupoId}/${currentTipo}`);
        const data = await res.json();

        if (data.success) {
            const g = data.data;
            document.getElementById('modalTitle').textContent = g.grupo ? g.grupo.nombre : 'Grupo';

            const colorClass = g.color || getColorClass(g.promedio);

            modalBody.innerHTML = `
                <div class="modal-kpi">
                    <span class="modal-kpi-value ${colorClass}">${g.promedio}</span>
                    <span class="modal-kpi-label">Promedio ${currentTipo === 'operativas' ? 'Operativo' : 'Seguridad'}</span>
                </div>
                <div class="modal-stats">
                    <div class="modal-stat">
                        <span class="stat-value">${g.total_supervisiones || 0}</span>
                        <span class="stat-label">Supervisiones</span>
                    </div>
                    <div class="modal-stat">
                        <span class="stat-value">${g.total_sucursales || 0}</span>
                        <span class="stat-label">Sucursales</span>
                    </div>
                </div>
                <h4 class="modal-section-title">Sucursales del Grupo</h4>
                <div class="modal-list">
                    ${(g.sucursales || []).map((s, i) => {
                        const sColorClass = s.color || getColorClass(s.promedio);
                        return `
                            <div class="modal-list-item" onclick="openSucursalDetailModal(${s.id})">
                                <span class="ranking-pos pos-${i + 1}">${i + 1}</span>
                                <div class="ranking-info">
                                    <span class="ranking-name">${s.nombre}</span>
                                    <span class="ranking-meta">${s.supervisiones || 0} supervisiones</span>
                                </div>
                                <span class="ranking-score ${sColorClass}">${s.promedio}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }
    } catch (e) {
        modalBody.innerHTML = '<div class="error-state">Error al cargar datos</div>';
    }
}

// ========== SUCURSAL DETAIL MODAL ==========
async function openSucursalDetailModal(sucursalId) {
    const modalBody = document.getElementById('sucursalModalBody');
    modalBody.innerHTML = '<div class="loading">Cargando...</div>';
    openSucursalModal();

    try {
        // Load detail and trend in parallel
        const [detailRes, trendRes] = await Promise.all([
            fetch(`/api/sucursal/${sucursalId}/${currentTipo}`),
            fetch(`/api/sucursal-tendencia/${sucursalId}/${currentTipo}`)
        ]);

        const detailData = await detailRes.json();
        const trendData = await trendRes.json();

        if (detailData.success) {
            const s = detailData.data;
            const sucInfo = s.sucursal || {};
            document.getElementById('sucursalModalTitle').textContent = sucInfo.nombre || 'Sucursal';

            const colorClass = s.color || getColorClass(s.promedio);

            // Build areas/KPIs section
            let areasHtml = '';
            if (s.areas && s.areas.length > 0) {
                const areaTitle = currentTipo === 'operativas' ? 'Areas Evaluadas' : 'KPIs de Seguridad';
                areasHtml = `
                    <h4 class="modal-section-title">${areaTitle}</h4>
                    <div class="areas-grid">
                        ${s.areas.map(a => {
                            const aColorClass = a.color || getColorClass(a.porcentaje);
                            return `
                                <div class="area-card ${aColorClass}">
                                    <span class="area-name">${a.nombre}</span>
                                    <span class="area-score">${a.porcentaje}</span>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            }

            // Build trend section
            let trendHtml = '';
            if (trendData.success && trendData.data.length > 0) {
                trendHtml = `
                    <h4 class="modal-section-title">Tendencia por Periodo</h4>
                    <div class="trend-chart">
                        ${trendData.data.map(t => {
                            const tColorClass = t.color || getColorClass(t.promedio);
                            const height = Math.max(20, (t.promedio / 100) * 80);
                            return `
                                <div class="trend-bar">
                                    <div class="trend-fill ${tColorClass}" style="height: ${height}%">
                                        <span class="trend-value">${t.promedio}</span>
                                    </div>
                                    <span class="trend-label">${(t.periodo || '').substring(0, 10)}</span>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            }

            modalBody.innerHTML = `
                <div class="modal-kpi">
                    <span class="modal-kpi-value ${colorClass}">${s.promedio}</span>
                    <span class="modal-kpi-label">${currentTipo === 'operativas' ? 'Calificacion Operativa' : 'Calificacion Seguridad'}</span>
                </div>
                <div class="modal-stats">
                    <div class="modal-stat">
                        <span class="stat-value">${s.supervisor || '-'}</span>
                        <span class="stat-label">Supervisor</span>
                    </div>
                    <div class="modal-stat">
                        <span class="stat-value">${sucInfo.grupo_nombre || '-'}</span>
                        <span class="stat-label">Grupo</span>
                    </div>
                </div>
                ${areasHtml}
                ${trendHtml}
            `;
        }
    } catch (e) {
        modalBody.innerHTML = '<div class="error-state">Error al cargar datos</div>';
    }
}

// ========== MAP ==========
function initMap() {
    if (map) return;

    const container = document.getElementById('mapContainer');
    map = L.map(container).setView([25.6866, -100.3161], 10); // Monterrey center

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap, &copy; CARTO',
        maxZoom: 19
    }).addTo(map);

    // Fix map size after tab switch
    setTimeout(() => map.invalidateSize(), 100);
}

async function loadMapData() {
    if (!map) return;

    // Clear existing markers
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    try {
        const res = await fetch(`/api/mapa/${currentTipo}`);
        const data = await res.json();

        if (data.success && data.data.length > 0) {
            const bounds = [];

            data.data.forEach(item => {
                if (!item.lat || !item.lng) return;

                const colorClass = item.color || getColorClass(item.promedio);
                const color = getMarkerColor(colorClass);

                const marker = L.circleMarker([item.lat, item.lng], {
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                }).addTo(map);

                marker.bindPopup(`
                    <div class="map-popup">
                        <strong>${item.nombre}</strong><br>
                        <span>${item.grupo || '-'}</span><br>
                        <span class="${colorClass}">${item.promedio}%</span>
                    </div>
                `);

                marker.on('click', () => openSucursalDetailModal(item.id));

                markers.push(marker);
                bounds.push([item.lat, item.lng]);
            });

            if (bounds.length > 0) {
                map.fitBounds(bounds, { padding: [20, 20] });
            }

            // Populate filter
            const filter = document.getElementById('mapFilter');
            const grupos = [...new Set(data.data.map(d => d.grupo).filter(Boolean))];
            filter.innerHTML = '<option value="todas">Todas las sucursales</option>' +
                grupos.map(g => `<option value="${g}">${g}</option>`).join('');
        }
    } catch (e) {
        console.error('Error loading map data:', e);
    }
}

function getMarkerColor(colorClass) {
    const colors = {
        'excellent': '#30d158',
        'good': '#5ac8fa',
        'regular': '#ffd60a',
        'critical': '#ff453a',
        'gray': '#8e8e93'
    };
    return colors[colorClass] || colors.gray;
}

// ========== HISTORICO ==========
async function loadHistorico() {
    const container = document.getElementById('heatmapContainer');
    container.innerHTML = '<div class="loading">Cargando...</div>';

    try {
        const res = await fetch(`/api/historico/${currentTipo}?territorio=all`);
        const data = await res.json();

        if (data.success && data.data) {
            const periodos = data.data.periodos || [];
            const grupos = data.data.grupos || [];
            const eplCas = data.data.epl_cas || {};

            if (grupos.length === 0) {
                container.innerHTML = '<div class="empty-state">No hay datos historicos</div>';
                return;
            }

            container.innerHTML = `
                <div class="heatmap-table">
                    <div class="heatmap-header">
                        <div class="heatmap-corner">Grupo</div>
                        ${periodos.map(p => `<div class="heatmap-period">${(p.nombre || '').substring(0, 12)}</div>`).join('')}
                    </div>
                    <div class="heatmap-body">
                        ${grupos.slice(0, 15).map(g => `
                            <div class="heatmap-row">
                                <div class="heatmap-entity">${g.nombre}</div>
                                ${periodos.map(p => {
                                    const periodoData = g.periodos[p.nombre] || {};
                                    const val = periodoData.promedio;
                                    const colorClass = periodoData.color || getColorClass(val);
                                    return `<div class="heatmap-cell ${colorClass}">${val !== null && val !== undefined ? val : '-'}</div>`;
                                }).join('')}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = '<div class="empty-state">No hay datos historicos</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar historico</div>';
    }
}

function formatPeriodo(periodo) {
    if (!periodo) return '-';
    const parts = periodo.split(' ');
    if (parts.length >= 2) {
        return parts[0].substring(0, 3) + ' ' + parts[1];
    }
    return periodo.substring(0, 10);
}

// ========== ALERTAS ==========
async function loadAlertas() {
    const critContainer = document.getElementById('alertasCriticos');
    const warnContainer = document.getElementById('alertasWarning');
    const summaryContainer = document.getElementById('alertasSummary');

    critContainer.innerHTML = '<div class="loading">Cargando...</div>';
    warnContainer.innerHTML = '<div class="loading">Cargando...</div>';

    try {
        const res = await fetch(`/api/alertas/${currentTipo}`);
        const data = await res.json();

        if (data.success && data.data) {
            const alertas = data.data.alertas || [];
            const criticos = alertas.filter(a => a.tipo === 'critical');
            const warning = alertas.filter(a => a.tipo === 'warning');

            // Summary
            summaryContainer.innerHTML = `
                <div class="alert-summary-card critical">
                    <span class="alert-count">${data.data.total_criticos || 0}</span>
                    <span class="alert-label">Criticos</span>
                </div>
                <div class="alert-summary-card warning">
                    <span class="alert-count">${data.data.total_warnings || 0}</span>
                    <span class="alert-label">En Riesgo</span>
                </div>
            `;

            // Critical list
            if (criticos.length > 0) {
                critContainer.innerHTML = criticos.map(item => `
                    <div class="alerta-item critical" onclick="openSucursalDetailModal(${item.sucursal_id})">
                        <div class="alerta-info">
                            <span class="alerta-name">${item.titulo}</span>
                            <span class="alerta-meta">${item.descripcion}</span>
                        </div>
                        <span class="alerta-score">${item.promedio}%</span>
                    </div>
                `).join('');
            } else {
                critContainer.innerHTML = '<div class="empty-state success-msg">Sin sucursales criticas</div>';
            }

            // Warning list
            if (warning.length > 0) {
                warnContainer.innerHTML = warning.map(item => `
                    <div class="alerta-item warning">
                        <div class="alerta-info">
                            <span class="alerta-name">${item.titulo}</span>
                            <span class="alerta-meta">${item.descripcion}</span>
                        </div>
                        <span class="alerta-score">${item.promedio}%</span>
                    </div>
                `).join('');
            } else {
                warnContainer.innerHTML = '<div class="empty-state success-msg">Sin grupos en riesgo</div>';
            }
        }
    } catch (e) {
        critContainer.innerHTML = '<div class="error-state">Error al cargar alertas</div>';
        warnContainer.innerHTML = '';
    }
}

// ========== HELPERS ==========
function getColorClass(value) {
    if (value === null || value === undefined || value === '-') return 'gray';
    const num = parseFloat(value);
    if (isNaN(num)) return 'gray';
    if (num >= 90) return 'excellent';
    if (num >= 80) return 'good';
    if (num >= 70) return 'regular';
    return 'critical';
}
