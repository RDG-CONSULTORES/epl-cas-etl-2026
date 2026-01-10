/**
 * EPL CAS 2026 - Dashboard Application
 * Frontend JavaScript - Simplified Version
 */

// State
let currentRankingType = 'grupos';
let grupos = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadPeriodos();
    loadGrupos();
    loadSucursales();
    loadRanking('grupos');
    initTabs();
    initRankingToggle();
});

// Tab Navigation
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });
}

// Ranking Toggle
function initRankingToggle() {
    document.querySelectorAll('.ranking-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.ranking-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadRanking(btn.dataset.ranking);
        });
    });
}

// Load Stats
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        if (data.success) {
            document.getElementById('totalPeriodos').textContent = data.data.total_periodos;
            document.getElementById('totalGrupos').textContent = data.data.total_grupos;
            document.getElementById('totalSucursales').textContent = data.data.total_sucursales;
            document.getElementById('promedioOperativo').textContent = data.data.promedio_operativo || '-';
        }
    } catch (e) {
        console.error('Error loading stats:', e);
    }
}

// Load Periodos
async function loadPeriodos() {
    const container = document.getElementById('periodosList');
    try {
        const res = await fetch('/api/periodos');
        const data = await res.json();
        if (data.success && data.data.length > 0) {
            container.innerHTML = data.data.map(p => `
                <div class="list-item ${p.activo ? 'active' : ''}">
                    <div class="item-main">
                        <span class="item-title">${p.nombre}</span>
                        <span class="item-subtitle">${p.fecha_inicio || ''} - ${p.fecha_fin || ''}</span>
                    </div>
                    <span class="item-badge ${p.activo ? 'success' : ''}">${p.activo ? 'Activo' : 'Inactivo'}</span>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="empty-state">No hay periodos registrados</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar periodos</div>';
    }
}

// Load Grupos
async function loadGrupos() {
    const container = document.getElementById('gruposList');
    const filter = document.getElementById('grupoFilter');
    try {
        const res = await fetch('/api/grupos-operativos');
        const data = await res.json();
        if (data.success && data.data.length > 0) {
            grupos = data.data;
            container.innerHTML = data.data.map(g => `
                <div class="list-item">
                    <div class="item-main">
                        <span class="item-title">${g.nombre}</span>
                        <span class="item-subtitle">Codigo: ${g.codigo || '-'}</span>
                    </div>
                    <span class="item-badge ${g.activo ? 'success' : ''}">${g.activo ? 'Activo' : 'Inactivo'}</span>
                </div>
            `).join('');

            // Populate filter
            filter.innerHTML = '<option value="">Todos los grupos</option>' +
                data.data.map(g => `<option value="${g.id}">${g.nombre}</option>`).join('');

            filter.addEventListener('change', () => loadSucursales(filter.value));
        } else {
            container.innerHTML = '<div class="empty-state">No hay grupos registrados</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar grupos</div>';
    }
}

// Load Sucursales
async function loadSucursales(grupoId = '') {
    const container = document.getElementById('sucursalesList');
    container.innerHTML = '<div class="loading">Cargando...</div>';
    try {
        const res = await fetch('/api/sucursales');
        const data = await res.json();
        if (data.success) {
            let sucursales = data.data;
            if (grupoId) {
                sucursales = sucursales.filter(s => s.grupo_operativo_id == grupoId);
            }
            if (sucursales.length > 0) {
                const grupoMap = {};
                grupos.forEach(g => grupoMap[g.id] = g.nombre);

                container.innerHTML = sucursales.map(s => `
                    <div class="list-item">
                        <div class="item-main">
                            <span class="item-title">${s.nombre}</span>
                            <span class="item-subtitle">${grupoMap[s.grupo_operativo_id] || 'Sin grupo'}</span>
                        </div>
                        <span class="item-badge ${s.activo ? 'success' : ''}">${s.activo ? 'Activa' : 'Inactiva'}</span>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<div class="empty-state">No hay sucursales</div>';
            }
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar sucursales</div>';
    }
}

// Load Ranking
async function loadRanking(type) {
    const container = document.getElementById('rankingList');
    container.innerHTML = '<div class="loading">Cargando...</div>';
    currentRankingType = type;

    try {
        const endpoint = type === 'grupos' ? '/api/ranking/grupos' : '/api/ranking/sucursales';
        const res = await fetch(endpoint);
        const data = await res.json();

        if (data.success && data.data.length > 0) {
            if (type === 'grupos') {
                container.innerHTML = data.data.map((item, i) => `
                    <div class="ranking-item">
                        <span class="ranking-pos">${i + 1}</span>
                        <div class="ranking-info">
                            <span class="ranking-name">${item.nombre}</span>
                            <span class="ranking-meta">${item.total_sucursales} sucursales</span>
                        </div>
                        <div class="ranking-scores">
                            <span class="score op" title="Operativo">${item.promedio_operativo}</span>
                            <span class="score seg" title="Seguridad">${item.promedio_seguridad}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = data.data.map((item, i) => `
                    <div class="ranking-item">
                        <span class="ranking-pos">${i + 1}</span>
                        <div class="ranking-info">
                            <span class="ranking-name">${item.nombre}</span>
                            <span class="ranking-meta">${item.grupo_nombre || '-'}</span>
                        </div>
                        <div class="ranking-scores">
                            <span class="score op" title="Operativo">${item.calificacion_operativa}</span>
                            <span class="score seg" title="Seguridad">${item.calificacion_seguridad}</span>
                        </div>
                    </div>
                `).join('');
            }
        } else {
            container.innerHTML = '<div class="empty-state">No hay datos de ranking</div>';
        }
    } catch (e) {
        container.innerHTML = '<div class="error-state">Error al cargar ranking</div>';
    }
}
