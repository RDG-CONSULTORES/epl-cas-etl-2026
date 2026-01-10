/**
 * EPL CAS 2026 - Dashboard Application
 * Frontend JavaScript
 */

// ============================================
// STATE
// ============================================

const state = {
    periodoId: null,
    tipo: 'operativas',
    view: 'grupos',
    map: null,
    markers: []
};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Get initial periodo from select
    const periodoSelect = document.getElementById('periodoSelect');
    state.periodoId = parseInt(periodoSelect.value);
    
    // Initialize event listeners
    initEventListeners();
    
    // Load initial data
    loadDashboard();
    loadAlertas();
});

function initEventListeners() {
    // Periodo select
    document.getElementById('periodoSelect').addEventListener('change', (e) => {
        state.periodoId = parseInt(e.target.value);
        refreshCurrentTab();
    });
    
    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });
    
    // Tipo toggles (Operativas/Seguridad)
    document.querySelectorAll('.tipo-toggle').forEach(toggle => {
        toggle.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                toggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.tipo = btn.dataset.tipo;
                refreshCurrentTab();
            });
        });
    });
    
    // View toggle (Grupos/Sucursales)
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.view = btn.dataset.view;
            loadRanking();
        });
    });
    
    // Close modal on backdrop click
    document.getElementById('detail-modal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            closeModal();
        }
    });
    
    // Close modal on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
}

// ============================================
// TAB NAVIGATION
// ============================================

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
    
    // Load tab data
    switch (tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'mapa':
            loadMapa();
            break;
        case 'historico':
            loadHistorico();
            break;
        case 'alertas':
            loadAlertas();
            break;
    }
}

function refreshCurrentTab() {
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab) {
        switchTab(activeTab.dataset.tab);
    }
}

// ============================================
// DASHBOARD
// ============================================

async function loadDashboard() {
    try {
        const response = await fetch(`/api/dashboard/${state.tipo}/${state.periodoId}`);
        const data = await response.json();
        
        // Update KPIs
        const kpis = data.kpis;
        
        const promedioEl = document.getElementById('kpi-promedio');
        promedioEl.textContent = kpis.promedio.toFixed(1);
        promedioEl.parentElement.className = `kpi-card main-kpi ${kpis.color}`;
        
        // Trend
        const trendEl = document.getElementById('kpi-trend');
        if (kpis.promedio_anterior !== null) {
            const diff = kpis.promedio - kpis.promedio_anterior;
            const sign = diff >= 0 ? '+' : '';
            trendEl.textContent = `${sign}${diff.toFixed(1)} vs periodo anterior`;
            trendEl.className = `kpi-trend ${kpis.tendencia}`;
        } else {
            trendEl.textContent = '';
        }
        
        document.getElementById('kpi-supervisiones').textContent = 
            `${kpis.sucursales_supervisadas}/${kpis.total_sucursales}`;
        document.getElementById('kpi-cobertura').textContent = `${kpis.cobertura}%`;
        
        // Load ranking
        loadRanking();
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadRanking() {
    const container = document.getElementById('ranking-container');
    container.innerHTML = '<div class="loading">Cargando...</div>';
    
    try {
        const endpoint = state.view === 'grupos' 
            ? `/api/ranking/grupos/${state.tipo}/${state.periodoId}`
            : `/api/ranking/sucursales/${state.tipo}/${state.periodoId}`;
        
        const response = await fetch(endpoint);
        const data = await response.json();
        
        if (data.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                    <p>No hay datos para este periodo</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = data.map(item => `
            <div class="ranking-item" onclick="openDetail('${state.view === 'grupos' ? 'grupo' : 'sucursal'}', ${item.id})">
                <div class="ranking-pos">${item.posicion}</div>
                <div class="ranking-info">
                    <div class="ranking-name">${item.nombre}</div>
                    <div class="ranking-meta">${item.supervisiones} supervisiones${item.grupo ? ` • ${item.grupo}` : ''}</div>
                </div>
                <div class="ranking-score">
                    <span class="score-value ${item.color}">${item.promedio.toFixed(1)}</span>
                    ${item.tendencia ? `<span class="trend-icon ${item.tendencia}">${getTrendIcon(item.tendencia)}</span>` : ''}
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading ranking:', error);
        container.innerHTML = '<div class="empty-state"><p>Error al cargar datos</p></div>';
    }
}

function getTrendIcon(trend) {
    switch (trend) {
        case 'up': return '↑';
        case 'down': return '↓';
        default: return '';
    }
}

// ============================================
// MAPA
// ============================================

async function loadMapa() {
    // Initialize map if not exists
    if (!state.map) {
        state.map = L.map('map', {
            center: [23.6345, -102.5528], // México center
            zoom: 5,
            zoomControl: true
        });
        
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap, &copy; CARTO',
            maxZoom: 19
        }).addTo(state.map);
    }
    
    // Clear existing markers
    state.markers.forEach(m => m.remove());
    state.markers = [];
    
    try {
        const response = await fetch(`/api/mapa/${state.tipo}/${state.periodoId}`);
        const data = await response.json();
        
        data.forEach(loc => {
            const marker = L.marker([loc.lat, loc.lng], {
                icon: L.divIcon({
                    className: 'custom-marker-wrapper',
                    html: `<div class="custom-marker ${loc.color}"></div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                })
            });
            
            const popupContent = `
                <div class="popup-content">
                    <h4>${loc.nombre}</h4>
                    <p>${loc.ciudad}, ${loc.estado}</p>
                    ${loc.grupo ? `<p>Grupo: ${loc.grupo}</p>` : ''}
                    <p class="score ${loc.color}">
                        ${loc.promedio !== null ? loc.promedio.toFixed(1) + '%' : 'Sin datos'}
                    </p>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            marker.on('click', () => {
                if (loc.supervisada) {
                    openDetail('sucursal', loc.id);
                }
            });
            
            marker.addTo(state.map);
            state.markers.push(marker);
        });
        
        // Fit bounds if markers exist
        if (state.markers.length > 0) {
            const group = L.featureGroup(state.markers);
            state.map.fitBounds(group.getBounds().pad(0.1));
        }
        
        // Force map resize (needed when tab is shown)
        setTimeout(() => state.map.invalidateSize(), 100);
        
    } catch (error) {
        console.error('Error loading map:', error);
    }
}

// ============================================
// HISTÓRICO
// ============================================

async function loadHistorico() {
    const container = document.getElementById('historico-container');
    container.innerHTML = '<div class="loading">Cargando...</div>';
    
    try {
        const response = await fetch(`/api/historico/${state.tipo}`);
        const data = await response.json();
        
        if (data.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No hay datos históricos</p></div>';
            return;
        }
        
        // Group by year
        const byYear = {};
        data.forEach(item => {
            if (!byYear[item.anio]) {
                byYear[item.anio] = [];
            }
            byYear[item.anio].push(item);
        });
        
        let html = '';
        Object.keys(byYear).sort((a, b) => b - a).forEach(year => {
            html += `
                <div class="historico-year">
                    <h3>${year}</h3>
                    ${byYear[year].map(item => `
                        <div class="historico-card">
                            <div class="historico-periodo">
                                <h4>${item.nombre}</h4>
                                <p>${item.supervisiones} supervisiones</p>
                            </div>
                            <div class="historico-score">
                                <div class="score ${item.color}">${item.promedio ? item.promedio.toFixed(1) : '--'}</div>
                                <div class="count">promedio</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading historico:', error);
        container.innerHTML = '<div class="empty-state"><p>Error al cargar datos</p></div>';
    }
}

// ============================================
// ALERTAS
// ============================================

async function loadAlertas() {
    const container = document.getElementById('alertas-container');
    container.innerHTML = '<div class="loading">Cargando...</div>';
    
    try {
        const response = await fetch(`/api/alertas/${state.tipo}/${state.periodoId}`);
        const data = await response.json();
        
        // Update badge
        const badge = document.getElementById('alertas-badge');
        const totalAlertas = data.total_criticos + data.total_sin_supervisar;
        if (totalAlertas > 0) {
            badge.textContent = totalAlertas;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
        
        let html = '';
        
        // Críticos
        html += `
            <div class="alerta-section criticos">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                    Críticos (${data.total_criticos})
                </h3>
        `;
        
        if (data.criticos.length > 0) {
            html += data.criticos.map(item => `
                <div class="alerta-item" onclick="openDetail('sucursal', ${item.id})">
                    <div class="alerta-info">
                        <div class="nombre">${item.nombre}</div>
                        <div class="fecha">${item.fecha}</div>
                    </div>
                    <div class="alerta-score ${item.color}">${item.calificacion}%</div>
                </div>
            `).join('');
        } else {
            html += '<div class="empty-state"><p>Sin alertas críticas 🎉</p></div>';
        }
        
        html += '</div>';
        
        // Sin supervisar
        html += `
            <div class="alerta-section sin-supervisar">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                    Sin Supervisar (${data.total_sin_supervisar})
                </h3>
        `;
        
        if (data.sin_supervisar.length > 0) {
            html += data.sin_supervisar.slice(0, 10).map(item => `
                <div class="alerta-item">
                    <div class="alerta-info">
                        <div class="nombre">${item.nombre}</div>
                        <div class="fecha">Suc. #${item.numero}</div>
                    </div>
                </div>
            `).join('');
            
            if (data.sin_supervisar.length > 10) {
                html += `<div class="alerta-item"><div class="alerta-info"><div class="nombre">... y ${data.sin_supervisar.length - 10} más</div></div></div>`;
            }
        } else {
            html += '<div class="empty-state"><p>Todas las sucursales supervisadas 🎉</p></div>';
        }
        
        html += '</div>';
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading alertas:', error);
        container.innerHTML = '<div class="empty-state"><p>Error al cargar datos</p></div>';
    }
}

// ============================================
// DETAIL MODAL
// ============================================

async function openDetail(type, id) {
    const modal = document.getElementById('detail-modal');
    const modalBody = document.getElementById('modal-body');
    const modalTitle = document.getElementById('modal-title');
    
    modal.classList.add('active');
    modalBody.innerHTML = '<div class="loading">Cargando...</div>';
    
    try {
        const endpoint = type === 'grupo' 
            ? `/api/detalle/grupo/${id}/${state.tipo}/${state.periodoId}`
            : `/api/detalle/sucursal/${id}/${state.tipo}/${state.periodoId}`;
        
        const response = await fetch(endpoint);
        const data = await response.json();
        
        if (type === 'grupo') {
            modalTitle.textContent = data.grupo.nombre;
            modalBody.innerHTML = renderGrupoDetail(data);
        } else {
            modalTitle.textContent = data.sucursal.nombre;
            modalBody.innerHTML = renderSucursalDetail(data);
        }
        
    } catch (error) {
        console.error('Error loading detail:', error);
        modalBody.innerHTML = '<div class="empty-state"><p>Error al cargar datos</p></div>';
    }
}

function renderGrupoDetail(data) {
    return `
        <div class="detail-header">
            <div class="detail-score ${data.color}">${data.promedio ? data.promedio.toFixed(1) : '--'}</div>
            <div class="detail-meta">Promedio del grupo</div>
        </div>
        
        <div class="detail-section">
            <h4>Tendencia</h4>
            <div class="detail-chart">
                ${data.tendencia.map(t => `
                    <div class="chart-bar">
                        <div class="bar ${getColorClass(t.promedio)}" style="height: ${t.promedio ? t.promedio : 0}%"></div>
                        <div class="bar-value">${t.promedio ? t.promedio : '--'}</div>
                        <div class="bar-label">${t.periodo}</div>
                    </div>
                `).join('')}
            </div>
        </div>
        
        <div class="detail-section">
            <h4>Sucursales (${data.sucursales.length})</h4>
            <div class="detail-list">
                ${data.sucursales.map(s => `
                    <div class="detail-item" onclick="openDetail('sucursal', ${s.id})">
                        <span class="detail-item-name">${s.nombre}</span>
                        <span class="detail-item-value ${s.color}">${s.promedio ? s.promedio.toFixed(1) : '--'}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function renderSucursalDetail(data) {
    const tipoLabel = state.tipo === 'operativas' ? 'Áreas' : 'KPIs';
    
    return `
        <div class="detail-header">
            <div class="detail-score ${data.color}">${data.calificacion ? data.calificacion.toFixed(1) : '--'}</div>
            <div class="detail-meta">
                ${data.sucursal.grupo ? `Grupo: ${data.sucursal.grupo}` : ''}<br>
                ${data.sucursal.ciudad}, ${data.sucursal.estado}<br>
                ${data.fecha ? `Fecha: ${data.fecha}` : ''} • Ranking: #${data.ranking}
            </div>
        </div>
        
        <div class="detail-section">
            <h4>Tendencia</h4>
            <div class="detail-chart">
                ${data.tendencia.map(t => `
                    <div class="chart-bar">
                        <div class="bar ${getColorClass(t.promedio)}" style="height: ${t.promedio ? t.promedio : 0}%"></div>
                        <div class="bar-value">${t.promedio ? t.promedio : '--'}</div>
                        <div class="bar-label">${t.periodo}</div>
                    </div>
                `).join('')}
            </div>
        </div>
        
        <div class="detail-section">
            <h4>${tipoLabel} (${data.detalle.length})</h4>
            <div class="detail-list">
                ${data.detalle.map(item => `
                    <div class="detail-item">
                        <span class="detail-item-name">${item.nombre}</span>
                        <div class="detail-item-bar">
                            <div class="detail-item-bar-fill ${item.color}" style="width: ${item.porcentaje || 0}%"></div>
                        </div>
                        <span class="detail-item-value ${item.color}">${item.porcentaje ? item.porcentaje.toFixed(1) : '--'}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function closeModal() {
    document.getElementById('detail-modal').classList.remove('active');
}

// ============================================
// UTILITIES
// ============================================

function getColorClass(value) {
    if (value === null || value === undefined) return 'gray';
    if (value >= 90) return 'green';
    if (value >= 80) return 'yellow';
    if (value >= 70) return 'orange';
    return 'red';
}
