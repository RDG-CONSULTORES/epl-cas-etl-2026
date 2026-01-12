/**
 * EPL CAS 2026 - Dashboard Application
 * Simplified and robust version
 */

// State
let currentTipo = 'operativas';
let currentView = 'grupos';
let currentTerritorio = 'todas';
let map = null;
let markers = [];

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    initToggles();
    initTabs();
    loadDashboard();
});

// ========== TOGGLES ==========
function initToggles() {
    // Main toggle: Operativas / Seguridad
    document.querySelectorAll('.toggle-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.toggle-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentTipo = btn.dataset.tipo;
            loadDashboard();
        });
    });

    // Sub toggle: Grupos / Sucursales
    document.querySelectorAll('.sub-toggle[data-view]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.sub-toggle[data-view]').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentView = btn.dataset.view;
            var title = document.getElementById('rankingTitle');
            if (title) title.textContent = currentView === 'grupos' ? 'de Grupos' : 'de Sucursales';
            loadRanking();
        });
    });

    // Territorio toggle
    document.querySelectorAll('.territorio-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.territorio-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentTerritorio = btn.dataset.territorio;
            loadRanking();
        });
    });
}

// ========== TABS ==========
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
            document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
            btn.classList.add('active');
            var tabId = btn.dataset.tab;
            var panel = document.getElementById(tabId);
            if (panel) panel.classList.add('active');

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

// ========== LOAD DASHBOARD ==========
function loadDashboard() {
    console.log('Loading dashboard for tipo:', currentTipo);
    loadKPIs();
    loadRanking();
}

// ========== KPIs ==========
function loadKPIs() {
    fetch('/api/kpis/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            console.log('KPIs response:', data);
            if (data.success && data.data) {
                var d = data.data;
                var promEl = document.getElementById('kpiPromedio');
                var totalEl = document.getElementById('kpiTotal');
                var gruposEl = document.getElementById('kpiGrupos');
                var sucEl = document.getElementById('kpiSucursales');

                if (promEl) {
                    promEl.textContent = d.promedio || '-';
                    promEl.className = 'kpi-value ' + (d.color || 'gray');
                }
                if (totalEl) totalEl.textContent = d.total_supervisiones || 0;
                if (gruposEl) gruposEl.textContent = d.total_grupos || 0;
                if (sucEl) sucEl.textContent = d.sucursales_supervisadas || 0;

                renderDistribution(d.distribucion || {});
            }
        })
        .catch(function(e) {
            console.error('Error loading KPIs:', e);
        });
}

function renderDistribution(dist) {
    var container = document.getElementById('distributionBars');
    if (!container) return;

    var total = (dist.excelente || 0) + (dist.bueno || 0) + (dist.regular || 0) + (dist.critico || 0);

    if (total === 0) {
        container.innerHTML = '<div class="empty-state">Sin datos</div>';
        return;
    }

    var items = [
        { label: 'Excelente', count: dist.excelente || 0, cls: 'excellent' },
        { label: 'Bueno', count: dist.bueno || 0, cls: 'good' },
        { label: 'Regular', count: dist.regular || 0, cls: 'regular' },
        { label: 'Critico', count: dist.critico || 0, cls: 'critical' }
    ];

    var html = items.map(function(item) {
        var pct = Math.round((item.count / total) * 100);
        return '<div class="dist-bar">' +
            '<div class="dist-label">' +
            '<span class="dist-name ' + item.cls + '">' + item.label + '</span>' +
            '<span class="dist-count">' + item.count + ' (' + pct + '%)</span>' +
            '</div>' +
            '<div class="dist-track">' +
            '<div class="dist-fill ' + item.cls + '" style="width: ' + pct + '%"></div>' +
            '</div>' +
            '</div>';
    }).join('');

    container.innerHTML = html;
}

// ========== RANKING ==========
function loadRanking() {
    var container = document.getElementById('rankingList');
    if (!container) return;
    container.innerHTML = '<div class="loading">Cargando...</div>';

    var endpoint = currentView === 'grupos'
        ? '/api/ranking/grupos/' + currentTipo
        : '/api/ranking/sucursales/' + currentTipo;

    fetch(endpoint)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            console.log('Ranking response:', data);
            if (data.success && data.data && data.data.length > 0) {
                var items = data.data;

                // Filter by territorio
                if (currentTerritorio !== 'todas' && currentView === 'grupos') {
                    items = items.filter(function(item) {
                        return item.territorio === currentTerritorio;
                    });
                }

                if (items.length === 0) {
                    container.innerHTML = '<div class="empty-state">Sin resultados para este filtro</div>';
                    return;
                }

                var html = items.map(function(item, i) {
                    var pos = i + 1;
                    var posClass = pos <= 3 ? 'pos-' + pos : '';
                    var colorClass = item.color || getColorClass(item.promedio);

                    if (currentView === 'grupos') {
                        return '<div class="ranking-item" onclick="openGrupoModal(' + item.id + ')">' +
                            '<span class="ranking-pos ' + posClass + '">' + pos + '</span>' +
                            '<div class="ranking-info">' +
                            '<span class="ranking-name">' + item.nombre + '</span>' +
                            '<span class="ranking-meta">' + item.total_sucursales + ' sucursales | ' + item.territorio + '</span>' +
                            '</div>' +
                            '<span class="ranking-score ' + colorClass + '">' + item.promedio + '</span>' +
                            '</div>';
                    } else {
                        return '<div class="ranking-item" onclick="openSucursalModal(' + item.id + ')">' +
                            '<span class="ranking-pos ' + posClass + '">' + pos + '</span>' +
                            '<div class="ranking-info">' +
                            '<span class="ranking-name">' + item.nombre + '</span>' +
                            '<span class="ranking-meta">' + (item.grupo_nombre || '-') + '</span>' +
                            '</div>' +
                            '<span class="ranking-score ' + colorClass + '">' + item.promedio + '</span>' +
                            '</div>';
                    }
                }).join('');

                container.innerHTML = html;
            } else {
                container.innerHTML = '<div class="empty-state">No hay datos de ranking</div>';
            }
        })
        .catch(function(e) {
            console.error('Error loading ranking:', e);
            container.innerHTML = '<div class="error-state">Error al cargar ranking</div>';
        });
}

// ========== MODALS ==========
function openGrupoModal(grupoId) {
    var overlay = document.getElementById('modalOverlay');
    var body = document.getElementById('modalBody');
    var title = document.getElementById('modalTitle');

    if (!overlay || !body) return;

    body.innerHTML = '<div class="loading">Cargando...</div>';
    body.scrollTop = 0; // Reset scroll position
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';

    fetch('/api/grupo/' + grupoId + '/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var g = data.data;
                if (title) title.textContent = g.grupo ? g.grupo.nombre : 'Grupo';

                var colorClass = g.color || getColorClass(g.promedio);

                var sucursalesHtml = (g.sucursales || []).map(function(s, i) {
                    var sColorClass = s.color || getColorClass(s.promedio);
                    return '<div class="modal-list-item" onclick="openSucursalModal(' + s.id + ')">' +
                        '<span class="ranking-pos pos-' + (i + 1) + '">' + (i + 1) + '</span>' +
                        '<div class="ranking-info">' +
                        '<span class="ranking-name">' + s.nombre + '</span>' +
                        '<span class="ranking-meta">' + (s.supervisiones || 0) + ' supervisiones</span>' +
                        '</div>' +
                        '<span class="ranking-score ' + sColorClass + '">' + s.promedio + '</span>' +
                        '</div>';
                }).join('');

                body.innerHTML = '<div class="modal-kpi">' +
                    '<span class="modal-kpi-value ' + colorClass + '">' + g.promedio + '</span>' +
                    '<span class="modal-kpi-label">Promedio ' + (currentTipo === 'operativas' ? 'Operativo' : 'Seguridad') + '</span>' +
                    '</div>' +
                    '<div class="modal-stats">' +
                    '<div class="modal-stat"><span class="stat-value">' + (g.total_supervisiones || 0) + '</span><span class="stat-label">Supervisiones</span></div>' +
                    '<div class="modal-stat"><span class="stat-value">' + (g.total_sucursales || 0) + '</span><span class="stat-label">Sucursales</span></div>' +
                    '</div>' +
                    '<h4 class="modal-section-title">Sucursales del Grupo</h4>' +
                    '<div class="modal-list">' + sucursalesHtml + '</div>';
            }
        })
        .catch(function(e) {
            body.innerHTML = '<div class="error-state">Error al cargar datos</div>';
        });

    // Close handlers
    var closeBtn = document.getElementById('modalClose');
    if (closeBtn) {
        closeBtn.onclick = function() {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        };
    }
    overlay.onclick = function(e) {
        if (e.target === overlay) {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    };
}

function openSucursalModal(sucursalId) {
    var overlay = document.getElementById('sucursalModalOverlay');
    var body = document.getElementById('sucursalModalBody');
    var title = document.getElementById('sucursalModalTitle');

    if (!overlay || !body) return;

    body.innerHTML = '<div class="loading">Cargando...</div>';
    body.scrollTop = 0; // Reset scroll position
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Cargar datos de sucursal y tendencia en paralelo
    Promise.all([
        fetch('/api/sucursal/' + sucursalId + '/' + currentTipo).then(function(r) { return r.json(); }),
        fetch('/api/sucursal-tendencia/' + sucursalId + '/' + currentTipo).then(function(r) { return r.json(); })
    ]).then(function(results) {
        var sucData = results[0];
        var tendData = results[1];

        if (sucData.success && sucData.data) {
            var s = sucData.data;
            var sucInfo = s.sucursal || {};
            if (title) title.textContent = sucInfo.nombre || 'Sucursal';

            var colorClass = s.color || getColorClass(s.promedio);

            // Construir HTML de tendencia (últimas 4 supervisiones)
            var tendenciaHtml = '';
            if (tendData.success && tendData.data && tendData.data.length > 0) {
                var maxVal = 100;
                var barsHtml = tendData.data.map(function(t) {
                    var height = Math.max((t.calificacion / maxVal) * 100, 5);
                    var tColor = t.color || getColorClass(t.calificacion);
                    return '<div class="trend-bar">' +
                        '<div class="trend-fill ' + tColor + '" style="height: ' + height + '%">' +
                        '<span class="trend-value">' + t.calificacion + '</span>' +
                        '</div>' +
                        '<span class="trend-label">' + t.fecha + '</span>' +
                        '</div>';
                }).join('');

                tendenciaHtml = '<div class="tendencia-section">' +
                    '<h4 class="modal-section-title">Ultimas ' + tendData.data.length + ' Supervisiones</h4>' +
                    '<div class="trend-chart">' + barsHtml + '</div>' +
                    '</div>';
            }

            // Construir HTML de áreas/KPIs
            var areasHtml = '';
            var areasTitle = currentTipo === 'operativas' ? 'Areas Evaluadas (' + (s.areas ? s.areas.length : 0) + ')' : 'KPIs de Seguridad (' + (s.areas ? s.areas.length : 0) + ')';
            if (s.areas && s.areas.length > 0) {
                areasHtml = '<h4 class="modal-section-title">' + areasTitle + '</h4>' +
                    '<div class="areas-grid">' +
                    s.areas.map(function(a) {
                        var aColorClass = a.color || getColorClass(a.porcentaje);
                        return '<div class="area-card ' + aColorClass + '">' +
                            '<span class="area-name">' + a.nombre + '</span>' +
                            '<span class="area-score">' + a.porcentaje + '%</span>' +
                            '</div>';
                    }).join('') +
                    '</div>';
            } else {
                areasHtml = '<div class="empty-state">Sin datos de areas</div>';
            }

            // Info adicional
            var infoHtml = '';
            if (sucInfo.ciudad || sucInfo.estado) {
                infoHtml = '<div class="sucursal-location">' +
                    '<span class="location-icon">📍</span>' +
                    '<span>' + (sucInfo.ciudad || '') + (sucInfo.ciudad && sucInfo.estado ? ', ' : '') + (sucInfo.estado || '') + '</span>' +
                    '</div>';
            }

            body.innerHTML = '<div class="modal-kpi">' +
                '<span class="modal-kpi-value ' + colorClass + '">' + s.promedio + '%</span>' +
                '<span class="modal-kpi-label">' + (currentTipo === 'operativas' ? 'Calificacion Operativa' : 'Calificacion Seguridad') + '</span>' +
                (s.fecha_supervision ? '<span class="modal-kpi-date">Ultima: ' + s.fecha_supervision.split(' ')[0] + '</span>' : '') +
                '</div>' +
                infoHtml +
                '<div class="modal-stats">' +
                '<div class="modal-stat"><span class="stat-value">' + (s.supervisor || '-') + '</span><span class="stat-label">Supervisor</span></div>' +
                '<div class="modal-stat"><span class="stat-value">' + (sucInfo.grupo_nombre || '-') + '</span><span class="stat-label">Grupo</span></div>' +
                '</div>' +
                tendenciaHtml +
                areasHtml;
        } else {
            body.innerHTML = '<div class="error-state">No se encontraron datos</div>';
        }
    }).catch(function(e) {
        console.error('Error loading sucursal:', e);
        body.innerHTML = '<div class="error-state">Error al cargar datos</div>';
    });

    // Close handlers
    var closeBtn = document.getElementById('sucursalModalClose');
    if (closeBtn) {
        closeBtn.onclick = function() {
            overlay.classList.remove('active');
            // Solo restaurar overflow si no hay otro modal activo
            var grupoModal = document.getElementById('modalOverlay');
            if (!grupoModal || !grupoModal.classList.contains('active')) {
                document.body.style.overflow = '';
            }
        };
    }
    var backBtn = document.getElementById('modalBack');
    if (backBtn) {
        backBtn.onclick = function() {
            overlay.classList.remove('active');
            // Al dar back, el modal de grupo sigue activo, no restaurar overflow
        };
    }
    overlay.onclick = function(e) {
        if (e.target === overlay) {
            overlay.classList.remove('active');
            var grupoModal = document.getElementById('modalOverlay');
            if (!grupoModal || !grupoModal.classList.contains('active')) {
                document.body.style.overflow = '';
            }
        }
    };
}

// ========== MAP ==========
function initMap() {
    if (map) return;

    var container = document.getElementById('mapContainer');
    if (!container) return;

    map = L.map(container).setView([25.6866, -100.3161], 10);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: 'OpenStreetMap, CARTO',
        maxZoom: 19
    }).addTo(map);

    setTimeout(function() { map.invalidateSize(); }, 100);
}

function loadMapData() {
    if (!map) return;

    markers.forEach(function(m) { map.removeLayer(m); });
    markers = [];

    fetch('/api/mapa/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data && data.data.length > 0) {
                var bounds = [];

                data.data.forEach(function(item) {
                    if (!item.lat || !item.lng) return;

                    var colorClass = item.color || getColorClass(item.promedio);
                    var color = getMarkerColor(colorClass);

                    var marker = L.circleMarker([item.lat, item.lng], {
                        radius: 10,
                        fillColor: color,
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9
                    }).addTo(map);

                    // Popup con botón para ver detalle
                    var popupContent = '<div class="map-popup">' +
                        '<strong>' + item.nombre + '</strong><br>' +
                        '<span class="popup-grupo">' + (item.grupo || '-') + '</span><br>' +
                        '<span class="popup-score ' + colorClass + '">' + item.promedio + '%</span><br>' +
                        '<button class="popup-btn" onclick="openSucursalModal(' + item.id + ')">Ver Detalle</button>' +
                        '</div>';

                    marker.bindPopup(popupContent);

                    // También abrir modal al hacer click directamente en el marker
                    marker.on('dblclick', function() {
                        openSucursalModal(item.id);
                    });

                    markers.push(marker);
                    bounds.push([item.lat, item.lng]);
                });

                if (bounds.length > 0) {
                    map.fitBounds(bounds, { padding: [20, 20] });
                }
            }
        })
        .catch(function(e) {
            console.error('Error loading map:', e);
        });
}

function getMarkerColor(colorClass) {
    var colors = {
        'excellent': '#30d158',
        'good': '#5ac8fa',
        'regular': '#ffd60a',
        'critical': '#ff453a',
        'gray': '#8e8e93'
    };
    return colors[colorClass] || colors.gray;
}

// ========== HISTORICO ==========
function loadHistorico() {
    var container = document.getElementById('heatmapContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading">Cargando...</div>';

    fetch('/api/historico/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var periodos = data.data.periodos || [];
                var grupos = data.data.grupos || [];

                if (grupos.length === 0) {
                    container.innerHTML = '<div class="empty-state">No hay datos historicos</div>';
                    return;
                }

                var headerHtml = periodos.map(function(p) {
                    return '<div class="heatmap-period">' + ((p.nombre || '').substring(0, 12)) + '</div>';
                }).join('');

                var bodyHtml = grupos.slice(0, 15).map(function(g) {
                    var cellsHtml = periodos.map(function(p) {
                        var periodoData = g.periodos[p.nombre] || {};
                        var val = periodoData.promedio;
                        var colorClass = periodoData.color || getColorClass(val);
                        var display = (val !== null && val !== undefined) ? val : '-';
                        return '<div class="heatmap-cell ' + colorClass + '">' + display + '</div>';
                    }).join('');

                    return '<div class="heatmap-row">' +
                        '<div class="heatmap-entity">' + g.nombre + '</div>' +
                        cellsHtml +
                        '</div>';
                }).join('');

                container.innerHTML = '<div class="heatmap-table">' +
                    '<div class="heatmap-header">' +
                    '<div class="heatmap-corner">Grupo</div>' +
                    headerHtml +
                    '</div>' +
                    '<div class="heatmap-body">' + bodyHtml + '</div>' +
                    '</div>';
            } else {
                container.innerHTML = '<div class="empty-state">No hay datos historicos</div>';
            }
        })
        .catch(function(e) {
            console.error('Error loading historico:', e);
            container.innerHTML = '<div class="error-state">Error al cargar historico</div>';
        });
}

// ========== ALERTAS ==========
function loadAlertas() {
    var critContainer = document.getElementById('alertasCriticos');
    var warnContainer = document.getElementById('alertasWarning');
    var summaryContainer = document.getElementById('alertasSummary');

    if (critContainer) critContainer.innerHTML = '<div class="loading">Cargando...</div>';
    if (warnContainer) warnContainer.innerHTML = '<div class="loading">Cargando...</div>';

    fetch('/api/alertas/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var alertas = data.data.alertas || [];
                var criticos = alertas.filter(function(a) { return a.tipo === 'critical'; });
                var warning = alertas.filter(function(a) { return a.tipo === 'warning'; });

                if (summaryContainer) {
                    summaryContainer.innerHTML = '<div class="alert-summary-card critical">' +
                        '<span class="alert-count">' + (data.data.total_criticos || 0) + '</span>' +
                        '<span class="alert-label">Criticos</span>' +
                        '</div>' +
                        '<div class="alert-summary-card warning">' +
                        '<span class="alert-count">' + (data.data.total_warnings || 0) + '</span>' +
                        '<span class="alert-label">En Riesgo</span>' +
                        '</div>';
                }

                if (critContainer) {
                    if (criticos.length > 0) {
                        critContainer.innerHTML = criticos.map(function(item) {
                            return '<div class="alerta-item critical" onclick="openSucursalModal(' + item.sucursal_id + ')">' +
                                '<div class="alerta-info">' +
                                '<span class="alerta-name">' + item.titulo + '</span>' +
                                '<span class="alerta-meta">' + item.descripcion + '</span>' +
                                '</div>' +
                                '<span class="alerta-score">' + item.promedio + '%</span>' +
                                '</div>';
                        }).join('');
                    } else {
                        critContainer.innerHTML = '<div class="empty-state success-msg">Sin sucursales criticas</div>';
                    }
                }

                if (warnContainer) {
                    if (warning.length > 0) {
                        warnContainer.innerHTML = warning.map(function(item) {
                            return '<div class="alerta-item warning">' +
                                '<div class="alerta-info">' +
                                '<span class="alerta-name">' + item.titulo + '</span>' +
                                '<span class="alerta-meta">' + item.descripcion + '</span>' +
                                '</div>' +
                                '<span class="alerta-score">' + item.promedio + '%</span>' +
                                '</div>';
                        }).join('');
                    } else {
                        warnContainer.innerHTML = '<div class="empty-state success-msg">Sin grupos en riesgo</div>';
                    }
                }
            }
        })
        .catch(function(e) {
            console.error('Error loading alertas:', e);
            if (critContainer) critContainer.innerHTML = '<div class="error-state">Error al cargar alertas</div>';
            if (warnContainer) warnContainer.innerHTML = '';
        });
}

// ========== HELPERS ==========
function getColorClass(value) {
    if (value === null || value === undefined || value === '-') return 'gray';
    var num = parseFloat(value);
    if (isNaN(num)) return 'gray';
    if (num >= 90) return 'excellent';
    if (num >= 80) return 'good';
    if (num >= 70) return 'regular';
    return 'critical';
}
