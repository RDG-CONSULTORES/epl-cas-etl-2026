/**
 * EPL CAS 2026 - Dashboard Application
 * Simplified and robust version
 */

// State
var currentTipo = 'operativas';
var currentView = 'grupos';
var currentTerritorio = 'todas';
var currentPeriodoId = null;
var currentPeriodo = null;
var periodosDisponibles = [];
var periodoActivoId = null; // ID del periodo marcado como activo
var map = null;
var markers = [];
var scrollPosition = 0; // Para guardar posición de scroll en iOS
var openModalsCount = 0; // Contador de modales abiertos

// ========== iOS MODAL FIX ==========
function lockBodyScroll() {
    if (openModalsCount === 0) {
        scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
        document.body.classList.add('modal-open');
        document.body.style.top = -scrollPosition + 'px';
    }
    openModalsCount++;
}

function unlockBodyScroll() {
    openModalsCount--;
    if (openModalsCount <= 0) {
        openModalsCount = 0;
        document.body.classList.remove('modal-open');
        document.body.style.top = '';
        window.scrollTo(0, scrollPosition);
    }
}

function forceRepaint(element) {
    // Forzar repaint en iOS
    if (element) {
        element.style.display = 'none';
        element.offsetHeight; // Trigger reflow
        element.style.display = '';
    }
}

// ========== THEME TOGGLE ==========
function initTheme() {
    // Cargar tema guardado o usar dark por defecto
    var savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // Inicializar toggle
    var toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.addEventListener('click', function() {
            toggleTheme();
        });
    }
}

function toggleTheme() {
    var html = document.documentElement;
    var currentTheme = html.getAttribute('data-theme') || 'dark';
    var newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    console.log('Theme changed to:', newTheme);
}

function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    initTheme();
    initToggles();
    initTabs();
    initPeriodSelector();
    loadPeriodoContexto(); // Cargar periodo primero, luego dashboard
});

// ========== PERIODO SELECTOR ==========
function initPeriodSelector() {
    var selector = document.getElementById('periodSelector');
    var overlay = document.getElementById('periodSheetOverlay');

    if (selector) {
        selector.addEventListener('click', function() {
            openPeriodSheet();
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                closePeriodSheet();
            }
        });
    }
}

function loadPeriodoContexto() {
    fetch('/api/periodo-contexto/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var d = data.data;

                // Guardar periodo actual
                if (d.periodo_actual) {
                    currentPeriodo = d.periodo_actual;
                    currentPeriodoId = d.periodo_actual.id;
                    periodoActivoId = d.periodo_actual.id; // Guardar el activo

                    // Actualizar UI
                    var periodName = document.getElementById('periodName');
                    if (periodName) {
                        periodName.textContent = d.periodo_actual.codigo || d.periodo_actual.nombre;
                    }
                }

                // Guardar lista de periodos con info de activo
                periodosDisponibles = (d.periodos || []).map(function(p) {
                    p.activo = (periodoActivoId && p.id == periodoActivoId);
                    return p;
                });

                // Actualizar progreso
                if (d.progreso) {
                    var progressText = document.getElementById('progressText');
                    if (progressText) {
                        progressText.textContent = d.progreso.supervisadas + '/' + d.progreso.total;
                    }
                }

                // Ahora cargar el dashboard con el periodo
                loadDashboard();
            }
        })
        .catch(function(e) {
            console.error('Error loading periodo contexto:', e);
            loadDashboard(); // Cargar dashboard aunque falle
        });
}

function openPeriodSheet() {
    var overlay = document.getElementById('periodSheetOverlay');
    var body = document.getElementById('periodSheetBody');
    var selector = document.getElementById('periodSelector');

    if (!overlay || !body) return;

    // Generar opciones - empezar con "Todos"
    var html = '';

    // Opción "Todos los periodos"
    var isAllSelected = currentPeriodoId === 'all';
    html += '<div class="period-option ' + (isAllSelected ? 'selected' : '') + '" data-id="all">' +
        '<div class="period-option-info">' +
            '<span class="period-option-name">Todos</span>' +
            '<span class="period-option-dates">Historico acumulado</span>' +
        '</div>' +
        '<div class="period-option-check">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">' +
                '<polyline points="20 6 9 17 4 12"/>' +
            '</svg>' +
        '</div>' +
    '</div>';

    // Separador
    html += '<div class="period-separator"></div>';

    // Periodos individuales
    periodosDisponibles.forEach(function(p) {
        var isSelected = currentPeriodoId && currentPeriodoId == p.id;
        var fechas = formatPeriodDates(p.fecha_inicio, p.fecha_fin);
        var isActivo = p.activo || (periodoActivoId && p.id == periodoActivoId);

        html += '<div class="period-option ' + (isSelected ? 'selected' : '') + '" data-id="' + p.id + '">' +
            '<div class="period-option-info">' +
                '<span class="period-option-name">' + (p.codigo || p.nombre) +
                    (isActivo ? ' <span class="period-activo-badge">Activo</span>' : '') +
                '</span>' +
                '<span class="period-option-dates">' + fechas + '</span>' +
            '</div>' +
            '<div class="period-option-check">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">' +
                    '<polyline points="20 6 9 17 4 12"/>' +
                '</svg>' +
            '</div>' +
        '</div>';
    });

    body.innerHTML = html;

    // Event listeners para las opciones
    body.querySelectorAll('.period-option').forEach(function(opt) {
        opt.addEventListener('click', function() {
            var periodoId = opt.dataset.id;
            if (periodoId === 'all') {
                selectPeriodo('all');
            } else {
                selectPeriodo(parseInt(periodoId));
            }
        });
    });

    if (selector) selector.classList.add('open');
    overlay.classList.add('active');
    lockBodyScroll();
}

function closePeriodSheet() {
    var overlay = document.getElementById('periodSheetOverlay');
    var selector = document.getElementById('periodSelector');

    if (selector) selector.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    unlockBodyScroll();
}

function selectPeriodo(periodoId) {
    var periodName = document.getElementById('periodName');

    if (periodoId === 'all') {
        // Seleccionar "Todos"
        currentPeriodoId = 'all';
        currentPeriodo = null;

        if (periodName) {
            periodName.textContent = 'Todos';
        }

        // Cerrar sheet y recargar
        closePeriodSheet();
        loadDashboard();
        // No actualizamos progreso porque es acumulado
        var progressText = document.getElementById('progressText');
        if (progressText) {
            progressText.textContent = 'Acumulado';
        }
        return;
    }

    // Encontrar el periodo en la lista
    var periodo = periodosDisponibles.find(function(p) { return p.id == periodoId; });

    if (periodo) {
        currentPeriodoId = periodo.id;
        currentPeriodo = periodo;

        // Actualizar UI
        if (periodName) {
            periodName.textContent = periodo.codigo || periodo.nombre;
        }

        // Cerrar sheet
        closePeriodSheet();

        // Recargar todo con el nuevo periodo
        loadDashboard();
        loadPeriodoProgreso();
    }
}

function loadPeriodoProgreso() {
    // Recargar solo el progreso
    fetch('/api/periodo-contexto/' + currentTipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data && data.data.progreso) {
                var progressText = document.getElementById('progressText');
                if (progressText) {
                    // Buscar progreso del periodo actual si es diferente
                    progressText.textContent = data.data.progreso.supervisadas + '/' + data.data.progreso.total;
                }
            }
        });
}

function formatPeriodDates(inicio, fin) {
    if (!inicio || !fin) return '';

    var meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

    try {
        var fi = new Date(inicio + 'T00:00:00');
        var ff = new Date(fin + 'T00:00:00');

        var diaI = fi.getDate();
        var mesI = meses[fi.getMonth()];
        var diaF = ff.getDate();
        var mesF = meses[ff.getMonth()];

        return diaI + ' ' + mesI + ' - ' + diaF + ' ' + mesF;
    } catch (e) {
        return inicio + ' - ' + fin;
    }
}

// ========== TOGGLES ==========
function initToggles() {
    // Main toggle: Operativas / Seguridad
    document.querySelectorAll('.toggle-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.toggle-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentTipo = btn.dataset.tipo;
            loadPeriodoContexto(); // Recargar contexto con nuevo tipo
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
    // Bottom navigation tabs (iOS style)
    document.querySelectorAll('.bottom-tab').forEach(function(btn) {
        btn.addEventListener('click', function() {
            // Remove active from all tabs
            document.querySelectorAll('.bottom-tab').forEach(function(b) { b.classList.remove('active'); });
            document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });

            // Add active to clicked tab
            btn.classList.add('active');
            var tabId = btn.dataset.tab;
            var panel = document.getElementById(tabId);
            if (panel) panel.classList.add('active');

            // Load tab-specific content
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
    var url = '/api/kpis/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }

    fetch(url)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            console.log('KPIs response:', data);
            if (data.success && data.data) {
                var d = data.data;
                var promEl = document.getElementById('kpiPromedio');
                var promLabelEl = document.getElementById('kpiPromedioLabel');
                var acumEl = document.getElementById('kpiAcumulado');
                var totalEl = document.getElementById('kpiTotal');
                var gruposEl = document.getElementById('kpiGrupos');
                var sucEl = document.getElementById('kpiSucursales');

                // Promedio principal
                if (promEl) {
                    promEl.textContent = d.promedio ? d.promedio + '%' : '-';
                    promEl.className = 'kpi-value ' + (d.color || 'gray');
                }

                // Label y acumulado
                if (currentPeriodoId === 'all') {
                    // Modo "Todos" - solo mostrar acumulado
                    if (promLabelEl) promLabelEl.textContent = 'Promedio Acumulado';
                    if (acumEl) acumEl.style.display = 'none';
                } else {
                    // Modo periodo específico - mostrar ambos
                    if (promLabelEl) promLabelEl.textContent = 'Promedio Periodo';
                    if (acumEl) {
                        acumEl.style.display = 'block';
                        acumEl.textContent = 'Acum: ' + (d.promedio_acumulado ? d.promedio_acumulado + '%' : '-');
                    }
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

    var params = [];
    if (currentPeriodoId) {
        params.push('periodo_id=' + currentPeriodoId);
    }
    // Filtro de territorio para sucursales
    if (currentView === 'sucursales' && currentTerritorio !== 'todas') {
        params.push('territorio=' + currentTerritorio);
    }
    if (params.length > 0) {
        endpoint += '?' + params.join('&');
    }

    fetch(endpoint)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            console.log('Ranking response:', data);
            if (data.success && data.data && data.data.length > 0) {
                var items = data.data;

                // Filter by territorio solo para grupos (ya se filtra en backend para sucursales)
                if (currentTerritorio !== 'todas' && currentView === 'grupos') {
                    items = items.filter(function(item) {
                        return item.territorio === currentTerritorio;
                    });
                }

                if (items.length === 0) {
                    container.innerHTML = '<div class="empty-state">Sin resultados para este filtro</div>';
                    return;
                }

                var html = items.map(function(item) {
                    // Usar posición del backend (con empates)
                    var pos = item.posicion;
                    var isPendiente = pos === null;
                    var posClass = pos && pos <= 3 ? 'pos-' + pos : '';
                    var colorClass = item.color || 'gray';
                    var promedio = item.promedio !== null ? item.promedio + '%' : 'Pendiente';

                    if (currentView === 'grupos') {
                        return '<div class="ranking-item ' + (isPendiente ? 'pendiente' : '') + '" onclick="openGrupoModal(' + item.id + ')">' +
                            '<span class="ranking-pos ' + posClass + '">' + (pos || '-') + '</span>' +
                            '<div class="ranking-info">' +
                            '<span class="ranking-name">' + item.nombre + '</span>' +
                            '<span class="ranking-meta">' + item.total_sucursales + ' sucursales | ' + item.territorio + '</span>' +
                            '</div>' +
                            '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
                            '</div>';
                    } else {
                        return '<div class="ranking-item ' + (isPendiente ? 'pendiente' : '') + '" onclick="openSucursalModal(' + item.id + ')">' +
                            '<span class="ranking-pos ' + posClass + '">' + (pos || '-') + '</span>' +
                            '<div class="ranking-info">' +
                            '<span class="ranking-name">' + item.nombre + '</span>' +
                            '<span class="ranking-meta">' + (item.grupo_nombre || '-') + '</span>' +
                            '</div>' +
                            '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
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
    var container = overlay ? overlay.querySelector('.modal-container') : null;

    if (!overlay || !body) return;

    // iOS fix: bloquear scroll del body
    lockBodyScroll();

    body.innerHTML = '<div class="loading">Cargando...</div>';
    body.scrollTop = 0;
    overlay.classList.add('active');

    // Forzar repaint para iOS
    forceRepaint(container);

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

                // Resetear scroll DESPUÉS de cargar contenido
                setTimeout(function() {
                    body.scrollTop = 0;
                    if (body.scrollTo) body.scrollTo(0, 0);
                }, 50);
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
            unlockBodyScroll();
        };
    }
    overlay.onclick = function(e) {
        if (e.target === overlay) {
            overlay.classList.remove('active');
            unlockBodyScroll();
        }
    };
}

function openSucursalModal(sucursalId) {
    var overlay = document.getElementById('sucursalModalOverlay');
    var body = document.getElementById('sucursalModalBody');
    var title = document.getElementById('sucursalModalTitle');
    var container = overlay ? overlay.querySelector('.modal-container') : null;

    if (!overlay || !body) return;

    // iOS fix: bloquear scroll (solo incrementa contador si ya hay modal abierto)
    lockBodyScroll();

    body.innerHTML = '<div class="loading">Cargando...</div>';
    body.scrollTop = 0;
    overlay.classList.add('active');

    // Forzar repaint para iOS - CRÍTICO
    forceRepaint(container);
    setTimeout(function() {
        forceRepaint(overlay);
    }, 10);

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
            var lastSupervisionId = null;
            if (tendData.success && tendData.data && tendData.data.length > 0) {
                var maxVal = 100;
                // Guardar el ID de la última supervisión (la más reciente está al final)
                lastSupervisionId = tendData.data[tendData.data.length - 1].id;

                var barsHtml = tendData.data.map(function(t, index) {
                    var height = Math.max((t.calificacion / maxVal) * 100, 5);
                    var tColor = t.color || getColorClass(t.calificacion);
                    var isLast = index === tendData.data.length - 1;
                    return '<div class="trend-bar ' + (isLast ? 'selected' : '') + '" data-sup-id="' + t.id + '" data-fecha="' + t.fecha + '" onclick="loadSupervisionAreas(' + t.id + ', this)">' +
                        '<div class="trend-fill ' + tColor + '" style="height: ' + height + '%">' +
                        '<span class="trend-value">' + t.calificacion + '</span>' +
                        '</div>' +
                        '<span class="trend-label">' + t.fecha + '</span>' +
                        '</div>';
                }).join('');

                tendenciaHtml = '<div class="tendencia-section">' +
                    '<h4 class="modal-section-title">Ultimas ' + tendData.data.length + ' Supervisiones</h4>' +
                    '<p class="trend-hint">Toca una barra para ver sus areas</p>' +
                    '<div class="trend-chart">' + barsHtml + '</div>' +
                    '</div>';
            }

            // Construir HTML de áreas/KPIs (en contenedor actualizable)
            var areasHtml = '';
            var areasTypeLabel = currentTipo === 'operativas' ? 'Areas Evaluadas' : 'KPIs de Seguridad';
            var areasCount = s.areas ? s.areas.length : 0;
            if (s.areas && s.areas.length > 0) {
                areasHtml = '<div id="areasContainer" data-tipo="' + currentTipo + '">' +
                    '<h4 class="modal-section-title" id="areasTitle">' + areasTypeLabel + ' (' + areasCount + ') - Ultima Supervision</h4>' +
                    '<div class="areas-grid" id="areasGrid">' +
                    s.areas.map(function(a) {
                        var aColorClass = a.color || getColorClass(a.porcentaje);
                        return '<div class="area-card ' + aColorClass + '">' +
                            '<span class="area-name">' + a.nombre + '</span>' +
                            '<span class="area-score">' + a.porcentaje + '%</span>' +
                            '</div>';
                    }).join('') +
                    '</div></div>';
            } else {
                areasHtml = '<div id="areasContainer"><div class="empty-state">Sin datos de areas</div></div>';
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

            // IMPORTANTE: Resetear scroll DESPUÉS de cargar contenido
            setTimeout(function() {
                body.scrollTop = 0;
                body.scrollTo && body.scrollTo(0, 0);
            }, 50);
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
            unlockBodyScroll(); // Decrementa contador, solo desbloquea si es el último
        };
    }
    var backBtn = document.getElementById('modalBack');
    if (backBtn) {
        backBtn.onclick = function() {
            overlay.classList.remove('active');
            unlockBodyScroll(); // Decrementa contador, el modal de grupo sigue activo
        };
    }
    overlay.onclick = function(e) {
        if (e.target === overlay) {
            overlay.classList.remove('active');
            unlockBodyScroll();
        }
    };
}

// Cargar áreas de una supervisión específica cuando se hace click en una barra
function loadSupervisionAreas(supervisionId, barElement) {
    var container = document.getElementById('areasContainer');
    var areasTitle = document.getElementById('areasTitle');
    var areasGrid = document.getElementById('areasGrid');
    var tipo = container ? container.getAttribute('data-tipo') : currentTipo;

    if (!container) return;

    // Marcar la barra como seleccionada
    var allBars = document.querySelectorAll('.trend-bar');
    allBars.forEach(function(bar) {
        bar.classList.remove('selected');
    });
    if (barElement) {
        barElement.classList.add('selected');
    }

    // Mostrar loading en las áreas
    if (areasGrid) {
        areasGrid.innerHTML = '<div class="loading-inline">Cargando...</div>';
    }

    // Obtener fecha de la barra para mostrar en el título
    var fecha = barElement ? barElement.getAttribute('data-fecha') : '';

    // Llamar al API
    fetch('/api/supervision/' + supervisionId + '/areas/' + tipo)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var d = data.data;
                var areasTypeLabel = tipo === 'operativas' ? 'Areas Evaluadas' : 'KPIs de Seguridad';

                // Actualizar título
                if (areasTitle) {
                    areasTitle.textContent = areasTypeLabel + ' (' + d.areas.length + ') - ' + d.fecha;
                }

                // Actualizar grid de áreas
                if (areasGrid && d.areas && d.areas.length > 0) {
                    areasGrid.innerHTML = d.areas.map(function(a) {
                        var aColorClass = a.color || getColorClass(a.porcentaje);
                        return '<div class="area-card ' + aColorClass + '">' +
                            '<span class="area-name">' + a.nombre + '</span>' +
                            '<span class="area-score">' + a.porcentaje + '%</span>' +
                            '</div>';
                    }).join('');
                } else if (areasGrid) {
                    areasGrid.innerHTML = '<div class="empty-state">Sin datos de areas para esta supervision</div>';
                }
            }
        })
        .catch(function(e) {
            console.error('Error loading supervision areas:', e);
            if (areasGrid) {
                areasGrid.innerHTML = '<div class="error-state">Error al cargar areas</div>';
            }
        });
}

// ========== MAP ==========
function initMap() {
    var container = document.getElementById('mapContainer');
    if (!container) return;

    // Si el mapa ya existe, solo invalidar tamaño y retornar
    if (map) {
        // Esperar a que el tab sea visible antes de invalidar
        setTimeout(function() {
            map.invalidateSize();
        }, 150);
        return;
    }

    // Crear mapa nuevo con tiles claros (CartoDB Voyager)
    map = L.map(container, {
        zoomControl: true,
        scrollWheelZoom: true
    }).setView([25.6866, -100.3161], 10);

    // Tiles claros - CartoDB Voyager (profesional y legible)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // Invalidar tamaño después de que el DOM esté listo
    setTimeout(function() {
        map.invalidateSize();
    }, 200);
}

function loadMapData() {
    if (!map) return;

    markers.forEach(function(m) { map.removeLayer(m); });
    markers = [];

    var url = '/api/mapa/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }

    fetch(url)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data && data.data.length > 0) {
                var bounds = [];

                data.data.forEach(function(item) {
                    if (!item.lat || !item.lng) return;

                    var colorClass = item.color || 'gray';
                    var color = getMarkerColor(colorClass);
                    var isPendiente = item.promedio === null;

                    var marker = L.circleMarker([item.lat, item.lng], {
                        radius: isPendiente ? 8 : 10,
                        fillColor: color,
                        color: '#fff',
                        weight: 2,
                        opacity: isPendiente ? 0.6 : 1,
                        fillOpacity: isPendiente ? 0.5 : 0.9
                    }).addTo(map);

                    // Popup con botón para ver detalle
                    var scoreText = isPendiente ? 'Pendiente' : item.promedio + '%';
                    var popupContent = '<div class="map-popup">' +
                        '<strong>' + item.nombre + '</strong><br>' +
                        '<span class="popup-grupo">' + (item.grupo || '-') + '</span><br>' +
                        '<span class="popup-score ' + colorClass + '">' + scoreText + '</span><br>' +
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
    // Colores optimizados para mapa claro (más saturados para mejor visibilidad)
    var colors = {
        'excellent': '#22c55e',  // Verde más visible
        'good': '#3b82f6',       // Azul más visible
        'regular': '#f59e0b',    // Amarillo/naranja más visible
        'critical': '#ef4444',   // Rojo más visible
        'gray': '#6b7280'
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

    var url = '/api/alertas/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }

    fetch(url)
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
