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

// Estado de agrupaciones expandidas/colapsadas
var agrupacionesEstado = {};

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

// ========== POPUP INFORMATIVO (reutilizable) ==========
function showInfoPopup(title, html) {
    var ov = document.createElement('div');
    ov.className = 'info-popup-overlay';
    ov.innerHTML = '<div class="info-popup">' +
        '<div class="info-popup-head"><span>' + title + '</span>' +
        '<button class="info-popup-close" aria-label="Cerrar">&times;</button></div>' +
        '<div class="info-popup-body">' + html + '</div></div>';
    document.body.appendChild(ov);
    function close() { if (ov.parentNode) ov.parentNode.removeChild(ov); }
    ov.addEventListener('click', function(e) { if (e.target === ov) close(); });
    ov.querySelector('.info-popup-close').addEventListener('click', close);
}

// Explica cómo se calcula el "Acumulado del Año" según el contexto
function showAcumuladoInfo(scope, anio) {
    var como;
    if (scope === 'sucursal') {
        como = 'Es el <strong>promedio</strong> de las calificaciones de esta sucursal en los trimestres del año ' + anio + ' (una visita por trimestre).';
    } else if (scope === 'grupo') {
        como = 'Es el <strong>promedio</strong> de las calificaciones de las sucursales del grupo durante los trimestres del año ' + anio + '. Cada sucursal pesa igual.';
    } else {
        como = 'Es el <strong>promedio</strong> de las calificaciones de los trimestres del año ' + anio + '. Cada sucursal pesa igual.';
    }
    showInfoPopup('¿Cómo se calcula el Acumulado del Año?',
        como + '<br><br>Solo cuenta lo de <strong>' + anio + '</strong> — no incluye años anteriores. Se reinicia cada 1 de enero.');
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

    // Opción "Acumulado del Año" = promedio de los trimestres del año en curso
    var isAllSelected = currentPeriodoId === 'all';
    html += '<div class="period-option ' + (isAllSelected ? 'selected' : '') + '" data-id="all">' +
        '<div class="period-option-info">' +
            '<span class="period-option-name">Año completo</span>' +
            '<span class="period-option-dates">Promedio de los trimestres del año en curso</span>' +
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
        var isFuturo = !!p.futuro && !isActivo;

        html += '<div class="period-option ' + (isSelected ? 'selected' : '') + (isFuturo ? ' disabled' : '') + '" data-id="' + p.id + '"' + (isFuturo ? ' aria-disabled="true"' : '') + '>' +
            '<div class="period-option-info">' +
                '<span class="period-option-name">' + (p.codigo || p.nombre) +
                    (isActivo ? ' <span class="period-activo-badge">En curso</span>' : '') +
                    (isFuturo ? ' <span class="period-futuro-badge">Próximo</span>' : '') +
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
            if (opt.classList.contains('disabled')) return; // trimestre futuro: aún no inicia
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
        // Seleccionar "Acumulado del Año"
        currentPeriodoId = 'all';
        currentPeriodo = null;

        if (periodName) {
            periodName.textContent = 'Año completo';
        }

        // Cerrar sheet y recargar
        closePeriodSheet();
        loadDashboard();
        // En modo año mostramos avance del año (revisadas / activas)
        var progressText = document.getElementById('progressText');
        if (progressText) {
            progressText.textContent = 'Año';
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
    // Recargar progreso del periodo seleccionado
    var url = '/api/periodo-contexto/' + currentTipo;
    if (currentPeriodoId && currentPeriodoId !== 'all') {
        url += '?periodo_id=' + currentPeriodoId;
    }
    fetch(url)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data && data.data.progreso) {
                var progressText = document.getElementById('progressText');
                if (progressText) {
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
function fmt1(v) {
    if (v === null || v === undefined || isNaN(parseFloat(v))) return '—';
    return (Math.round(parseFloat(v) * 10) / 10).toFixed(1);
}

function fmtFecha(iso) {
    if (!iso) return '';
    var meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    var p = iso.split('-');
    if (p.length < 3) return iso;
    return parseInt(p[2], 10) + ' ' + meses[parseInt(p[1], 10) - 1] + ' ' + p[0];
}

function loadKPIs() {
    var url = '/api/kpis/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }
    var el = function(id) { return document.getElementById(id); };

    fetch(url)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (!(data.success && data.data)) {
                if (el('kpiPromedio')) { el('kpiPromedio').textContent = '—'; el('kpiPromedio').className = 'kpi-value gray'; }
                if (el('kpiSub')) el('kpiSub').textContent = 'No se pudieron cargar los datos';
                return;
            }
            var d = data.data;
            var esAnio = (currentPeriodoId === 'all');
            var tipoTxt = (currentTipo === 'operativas') ? 'Operativa' : 'de Seguridad';
            var periodoTxt = esAnio
                ? ('Año ' + d.anio)
                : (((currentPeriodo && (currentPeriodo.codigo || currentPeriodo.nombre)) || 'Trimestre').replace('-', ' '));
            var tiene = (d.promedio !== null && d.promedio !== undefined);
            var faltan = (d.total_sucursales || 0) - (d.sucursales_supervisadas || 0);

            // 1) Tarjeta principal: qué mide · de qué periodo · sobre cuántas
            if (el('kpiPromedioLabel')) {
                el('kpiPromedioLabel').innerHTML = 'Calificación ' + tipoTxt + ' · ' + periodoTxt +
                    (d.en_curso ? ' <span class="pill pill-curso">En curso</span>' : (esAnio ? ' <span class="pill pill-muted">preliminar</span>' : ''));
            }
            if (el('kpiPromedio')) {
                el('kpiPromedio').textContent = tiene ? fmt1(d.promedio) : '—';
                el('kpiPromedio').className = 'kpi-value ' + (tiene ? (d.color || 'gray') : 'gray');
            }
            if (el('kpiSub')) {
                el('kpiSub').textContent = tiene
                    ? ((d.sucursales_supervisadas || 0) + ' de ' + (d.total_sucursales || 0) + ' sucursales supervisadas' +
                       ((d.en_curso && faltan > 0) ? ' · faltan ' + faltan : ''))
                    : 'Sin supervisiones en ' + periodoTxt;
            }

            // 2) Tendencia: siempre con signo; "preliminar" mientras el trimestre no cierre
            var trendEl = el('kpiTrend');
            if (trendEl) {
                var t = (!esAnio) ? d.tendencia : null;
                if (t && t.direccion) {
                    var arrow = t.direccion === 'up' ? '▲' : (t.direccion === 'down' ? '▼' : '≈');
                    trendEl.className = 'kpi-trend ' + t.direccion;
                    trendEl.innerHTML = arrow + ' ' + (t.delta > 0 ? '+' : '') + fmt1(t.delta) +
                        ' <span class="trend-vs">vs ' + t.vs + ' ' + d.anio + (t.prev !== undefined ? ' (' + fmt1(t.prev) + ')' : '') +
                        (t.preliminar ? ' · preliminar' : '') + '</span>';
                    trendEl.style.display = '';
                } else if (esAnio && d.delta_anual !== null && d.delta_anual !== undefined) {
                    var dirA = d.delta_anual >= 0.1 ? 'up' : (d.delta_anual <= -0.1 ? 'down' : 'flat');
                    trendEl.className = 'kpi-trend ' + dirA;
                    trendEl.innerHTML = (dirA === 'up' ? '▲' : (dirA === 'down' ? '▼' : '≈')) + ' ' + (d.delta_anual > 0 ? '+' : '') + fmt1(d.delta_anual) +
                        ' <span class="trend-vs">vs Año ' + d.anio_anterior + ' (' + fmt1(d.promedio_anio_anterior) + ')</span>';
                    trendEl.style.display = '';
                } else {
                    trendEl.style.display = 'none';
                    trendEl.innerHTML = '';
                }
            }

            // 3) Chips Q1..Q4 de la marca (tocar = seleccionar ese trimestre)
            var chips = el('qChips');
            if (chips) {
                chips.innerHTML = (d.trimestres || []).map(function(q) {
                    var qLbl = (q.codigo || '').split('-')[0];
                    var cls = 'q-chip' + (q.futuro ? ' off' : '') + (q.en_curso ? ' on' : '') + ((!esAnio && currentPeriodoId == q.id) ? ' sel' : '');
                    var val = q.futuro ? '—' : fmt1(q.promedio);
                    var vcls = q.futuro ? '' : getColorClass(q.promedio);
                    var sub = q.futuro ? 'Próximo' : (q.en_curso ? q.evaluadas + '/' + q.activas : (q.promedio === null ? 'sin datos' : qLbl === '' ? '' : q.evaluadas + '/' + q.activas));
                    return '<div class="' + cls + '" role="button" tabindex="0" ' + (q.futuro ? 'aria-disabled="true"' : 'onclick="selectPeriodo(' + q.id + ')"') +
                        ' aria-label="' + qLbl + ' ' + d.anio + '"><b class="' + vcls + '">' + val + '</b><span>' + qLbl + ' · ' + sub + '</span></div>';
                }).join('');
            }

            // 4) Año N (preliminar hasta cerrar Q4) y Año N-1 (cerrado, referencia)
            if (el('kpiAnioLabel')) el('kpiAnioLabel').textContent = 'Año ' + d.anio;
            if (el('kpiAnio')) {
                el('kpiAnio').textContent = fmt1(d.promedio_acumulado);
                el('kpiAnio').className = 'kpi-value mid ' + getColorClass(d.promedio_acumulado);
            }
            if (el('kpiAnioSub')) el('kpiAnioSub').textContent = (d.sucursales_anio || 0) + ' sucursales · preliminar';
            if (el('kpiPrevLabel')) el('kpiPrevLabel').textContent = 'Año ' + d.anio_anterior;
            var hayPrev = (d.promedio_anio_anterior !== null && d.promedio_anio_anterior !== undefined);
            if (el('kpiPrev')) el('kpiPrev').textContent = hayPrev ? fmt1(d.promedio_anio_anterior) : '—';
            if (el('kpiPrevSub')) el('kpiPrevSub').textContent = hayPrev ? ((d.sucursales_anio_anterior || 0) + ' sucursales · cerrado') : 'Sin datos';
            var deltaEl = el('kpiDelta');
            if (deltaEl) {
                if (hayPrev && d.delta_anual !== null && d.delta_anual !== undefined) {
                    var up = d.delta_anual >= 0;
                    deltaEl.className = 'pill pill-delta ' + (up ? 'pill-up' : 'pill-down');
                    deltaEl.textContent = (up ? '▲ +' : '▼ ') + fmt1(d.delta_anual);
                    deltaEl.style.display = '';
                } else {
                    deltaEl.style.display = 'none';
                }
            }

            // 5) Estado actual (M2) y grupos con datos
            if (el('kpiEstado')) {
                el('kpiEstado').textContent = fmt1(d.estado_actual);
                el('kpiEstado').className = 'kpi-value mid ' + getColorClass(d.estado_actual);
            }
            if (el('kpiGrupos')) el('kpiGrupos').innerHTML = (d.total_grupos || 0) + '<span class="kpi-de"> de ' + (d.total_grupos_catalogo || 0) + '</span>';
            if (el('kpiGruposSub')) el('kpiGruposSub').textContent = 'con supervisión en ' + periodoTxt;

            // 6) Fecha de corte de los datos
            if (el('dataCut')) {
                el('dataCut').textContent = (d.fecha_corte ? 'Datos al ' + fmtFecha(d.fecha_corte) + ' · Zenput' : '') +
                    (hayPrev ? ' · ' + d.anio_anterior + ' se auditó con otro calendario' : '');
            }

            // Barra de periodo: nombre + estado
            var periodName = el('periodName');
            if (periodName) periodName.textContent = periodoTxt + (d.en_curso ? ' · En curso' : '');
            var pt = el('progressText');
            if (pt) pt.textContent = (d.sucursales_supervisadas || 0) + '/' + (d.total_sucursales || 0);

            renderDistribution(d.distribucion || {});
        })
        .catch(function(e) {
            console.error('Error loading KPIs:', e);
            if (el('kpiPromedio')) { el('kpiPromedio').textContent = '—'; el('kpiPromedio').className = 'kpi-value gray'; }
            if (el('kpiSub')) el('kpiSub').textContent = 'No se pudieron cargar los datos';
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
    // Filtro de territorio
    if (currentTerritorio !== 'todas') {
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

                if (items.length === 0) {
                    container.innerHTML = '<div class="empty-state">Sin resultados para este filtro</div>';
                    return;
                }

                var html = '';

                if (currentView === 'grupos') {
                    // Vista de grupos con soporte para agrupaciones
                    items.forEach(function(item) {
                        if (item.tipo === 'agrupacion') {
                            html += renderAgrupacion(item);
                        } else {
                            html += renderGrupoItem(item);
                        }
                    });
                } else {
                    // Vista de sucursales (sin cambios)
                    html = items.map(function(item) {
                        var pos = item.posicion;
                        var isPendiente = pos === null;
                        var posClass = pos && pos <= 3 ? 'pos-' + pos : '';
                        var colorClass = item.color || 'gray';
                        var promedio = item.promedio !== null ? item.promedio + '%' : 'Pendiente';

                        return '<div class="ranking-item ' + (isPendiente ? 'pendiente' : '') + '" onclick="openSucursalModal(' + item.id + ')">' +
                            '<span class="ranking-pos ' + posClass + '">' + (pos || '-') + '</span>' +
                            '<div class="ranking-info">' +
                            '<span class="ranking-name">' + item.nombre + '</span>' +
                            '<span class="ranking-meta">' + (item.grupo_nombre || '-') + '</span>' +
                            '</div>' +
                            '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
                            '</div>';
                    }).join('');
                }

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

// Renderiza un grupo individual
function renderGrupoItem(item) {
    var pos = item.posicion;
    var isPendiente = pos === null;
    var posClass = pos && pos <= 3 ? 'pos-' + pos : '';
    var colorClass = item.color || 'gray';
    var promedio = item.promedio !== null ? item.promedio + '%' : 'Pendiente';

    return '<div class="ranking-item ' + (isPendiente ? 'pendiente' : '') + '" onclick="openGrupoModal(' + item.id + ')">' +
        '<span class="ranking-pos ' + posClass + '">' + (pos || '-') + '</span>' +
        '<div class="ranking-info">' +
        '<span class="ranking-name">' + item.nombre + '</span>' +
        '<span class="ranking-meta">' + item.total_sucursales + ' sucursales | ' + item.territorio + '</span>' +
        '</div>' +
        '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
        '</div>';
}

// Renderiza una agrupación con sus grupos anidados
function renderAgrupacion(agrupacion) {
    var isExpanded = agrupacionesEstado[agrupacion.id] === true;
    var colorClass = agrupacion.color || 'gray';
    var promedio = agrupacion.promedio !== null ? agrupacion.promedio + '%' : 'Pendiente';
    var pos = agrupacion.posicion;
    var posClass = pos && pos <= 3 ? 'pos-' + pos : '';

    // Renderizar grupos dentro de la agrupación
    var gruposHtml = '';
    if (agrupacion.grupos && agrupacion.grupos.length > 0) {
        gruposHtml = agrupacion.grupos.map(function(g) {
            var gPos = g.posicion_interna;
            var gPosClass = gPos && gPos <= 3 ? 'pos-' + gPos : '';
            var gColorClass = g.color || 'gray';
            var gPromedio = g.promedio !== null ? g.promedio + '%' : 'Pendiente';
            var gIsPendiente = g.promedio === null;

            return '<div class="ranking-item agrupacion-child ' + (gIsPendiente ? 'pendiente' : '') + '" onclick="openGrupoModal(' + g.id + ')">' +
                '<span class="ranking-pos ' + gPosClass + '">' + (gPos || '-') + '</span>' +
                '<div class="ranking-info">' +
                '<span class="ranking-name">' + g.nombre + '</span>' +
                '<span class="ranking-meta">' + g.total_sucursales + ' sucursales | ' + g.territorio + '</span>' +
                '</div>' +
                '<span class="ranking-score ' + gColorClass + '">' + gPromedio + '</span>' +
                '</div>';
        }).join('');
    }

    return '<div class="agrupacion-item ' + (isExpanded ? 'expanded' : '') + '" data-agrupacion="' + agrupacion.id + '">' +
        '<div class="agrupacion-header" onclick="toggleAgrupacion(\'' + agrupacion.id + '\')">' +
            '<span class="ranking-pos ' + posClass + '">' + (pos || '-') + '</span>' +
            '<svg class="agrupacion-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                '<polyline points="9 6 15 12 9 18"/>' +
            '</svg>' +
            '<div class="ranking-info">' +
                '<span class="ranking-name">' + agrupacion.nombre + '</span>' +
                '<span class="ranking-meta">' + agrupacion.total_grupos + ' grupos | ' + agrupacion.total_sucursales + ' sucursales</span>' +
            '</div>' +
            '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
        '</div>' +
        '<div class="agrupacion-body">' + gruposHtml + '</div>' +
    '</div>';
}

// Toggle expandir/colapsar agrupación
function toggleAgrupacion(agrupacionId) {
    agrupacionesEstado[agrupacionId] = !agrupacionesEstado[agrupacionId];
    var element = document.querySelector('[data-agrupacion="' + agrupacionId + '"]');
    if (element) {
        element.classList.toggle('expanded');
    }
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

    // Pasar el trimestre seleccionado para que el drill-down COINCIDA con el
    // ranking y el mapa (antes mostraba el histórico de todos los años).
    var grupoUrl = '/api/grupo/' + grupoId + '/' + currentTipo;
    if (currentPeriodoId) grupoUrl += '?periodo_id=' + currentPeriodoId;

    fetch(grupoUrl)
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success && data.data) {
                var g = data.data;
                if (title) title.textContent = g.grupo ? g.grupo.nombre : 'Grupo';

                var colorClass = g.color || getColorClass(g.promedio);

                var sucursalesHtml = (g.sucursales || []).map(function(s, i) {
                    var pendiente = !s.supervisiones;
                    var sColorClass = pendiente ? 'gray' : (s.color || getColorClass(s.promedio));
                    var scoreTxt = pendiente ? '—' : s.promedio;
                    var metaTxt = pendiente ? 'Sin revision este trimestre' : ((s.supervisiones || 0) + ' revision' + ((s.supervisiones || 0) === 1 ? '' : 'es'));
                    return '<div class="modal-list-item" onclick="openSucursalModal(' + s.id + ')">' +
                        '<span class="ranking-pos pos-' + (i + 1) + '">' + (i + 1) + '</span>' +
                        '<div class="ranking-info">' +
                        '<span class="ranking-name">' + s.nombre + '</span>' +
                        '<span class="ranking-meta">' + metaTxt + '</span>' +
                        '</div>' +
                        '<span class="ranking-score ' + sColorClass + '">' + scoreTxt + '</span>' +
                        '</div>';
                }).join('');

                // Tendencia por trimestre: chips que se "prenden" + flecha ↑/↓/▬
                var tendenciaHtml = '';
                if (g.tendencia && g.tendencia.length) {
                    var chips = g.tendencia.map(function(t) {
                        var qLabel = (t.codigo || '').split('-')[0];
                        var score = t.tiene_dato ? t.promedio : '—';
                        var arrow = '';
                        if (t.direccion === 'up') arrow = '<span class="trend-arrow up">▲</span>';
                        else if (t.direccion === 'down') arrow = '<span class="trend-arrow down">▼</span>';
                        else if (t.direccion === 'flat') arrow = '<span class="trend-arrow flat">▬</span>';
                        var deltaTxt = (t.delta !== null && t.delta !== undefined)
                            ? ((t.delta > 0 ? '+' : '') + t.delta) : '';
                        var cls = t.tiene_dato ? t.color : 'off';
                        return '<div class="trend-chip ' + cls + '" title="' + (t.nombre || '') +
                                (deltaTxt ? ' · ' + deltaTxt + ' vs trim. anterior' : '') + '">' +
                            '<span class="trend-q">' + qLabel + '</span>' +
                            '<span class="trend-score">' + score + '</span>' +
                            arrow +
                            '</div>';
                    }).join('');
                    var anioTxt = g.anio || '';
                    var promAnioHtml = '';
                    if (g.promedio_anio !== null && g.promedio_anio !== undefined) {
                        promAnioHtml = '<span class="trend-anio ' + (g.color_anio || 'gray') + '">' +
                            'Acumulado del Año ' + anioTxt + ': <strong>' + g.promedio_anio + '%</strong>' +
                            '<button class="info-i" onclick="showAcumuladoInfo(\'grupo\', ' + (anioTxt || 0) + ')" aria-label="Cómo se calcula">i</button></span>';
                    }
                    tendenciaHtml = '<div class="trend-head">' +
                        '<h4 class="modal-section-title">Tendencia por trimestre</h4>' +
                        promAnioHtml +
                        '</div>' +
                        '<div class="trend-chips">' + chips + '</div>';
                }

                var sinDatosGrupo = (g.promedio === null || g.promedio === undefined);
                var periodoLbl = (currentPeriodoId === 'all')
                    ? ('Acumulado del Año ' + (g.anio || ''))
                    : ((currentPeriodo && (currentPeriodo.codigo || currentPeriodo.nombre)) || 'Trimestre');
                var evalTxt = (g.sucursales_evaluadas !== undefined) ? (g.sucursales_evaluadas + ' de ' + (g.total_sucursales || 0) + ' sucursales') : '';
                body.innerHTML = '<div class="modal-kpi">' +
                    '<span class="modal-kpi-value ' + (sinDatosGrupo ? 'gray' : colorClass) + '">' + (sinDatosGrupo ? '—' : g.promedio + '%') + '</span>' +
                    '<span class="modal-kpi-label">' + (sinDatosGrupo
                        ? 'Sin supervisión · ' + periodoLbl
                        : 'Calificación ' + (currentTipo === 'operativas' ? 'Operativa' : 'de Seguridad') + ' · ' + periodoLbl + (evalTxt ? ' · ' + evalTxt : '')) + '</span>' +
                    '</div>' +
                    '<div class="modal-stats">' +
                    '<div class="modal-stat"><span class="stat-value">' + (g.total_supervisiones || 0) + '</span><span class="stat-label">Supervisiones</span></div>' +
                    '<div class="modal-stat"><span class="stat-value">' + (g.total_sucursales || 0) + '</span><span class="stat-label">Sucursales</span></div>' +
                    '</div>' +
                    tendenciaHtml +
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

    // El número/áreas reflejan el trimestre seleccionado (coincide con ranking/mapa).
    // La tendencia SÍ va sin periodo: muestra la historia trimestre a trimestre.
    var sucUrl = '/api/sucursal/' + sucursalId + '/' + currentTipo;
    if (currentPeriodoId) sucUrl += '?periodo_id=' + currentPeriodoId;

    // Cargar datos de sucursal y tendencia en paralelo
    Promise.all([
        fetch(sucUrl).then(function(r) { return r.json(); }),
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

            // Tendencia por trimestre (chips que se prenden + flecha), igual que el grupo
            var trendQHtml = '';
            if (s.tendencia && s.tendencia.length) {
                var sChips = s.tendencia.map(function(t) {
                    var qLabel = (t.codigo || '').split('-')[0];
                    var score = t.tiene_dato ? t.promedio : '—';
                    var arrow = '';
                    if (t.direccion === 'up') arrow = '<span class="trend-arrow up">▲</span>';
                    else if (t.direccion === 'down') arrow = '<span class="trend-arrow down">▼</span>';
                    else if (t.direccion === 'flat') arrow = '<span class="trend-arrow flat">▬</span>';
                    var deltaTxt = (t.delta !== null && t.delta !== undefined) ? ((t.delta > 0 ? '+' : '') + t.delta) : '';
                    var cls = t.tiene_dato ? t.color : 'off';
                    return '<div class="trend-chip ' + cls + '" title="' + (t.nombre || '') +
                            (deltaTxt ? ' · ' + deltaTxt + ' vs trim. anterior' : '') + '">' +
                        '<span class="trend-q">' + qLabel + '</span>' +
                        '<span class="trend-score">' + score + '</span>' + arrow +
                        '</div>';
                }).join('');
                var sPromAnioHtml = '';
                if (s.promedio_anio !== null && s.promedio_anio !== undefined) {
                    sPromAnioHtml = '<span class="trend-anio ' + (s.color_anio || 'gray') + '">' +
                        'Acumulado del Año ' + (s.anio || '') + ': <strong>' + s.promedio_anio + '%</strong>' +
                        '<button class="info-i" onclick="showAcumuladoInfo(\'sucursal\', ' + (s.anio || 0) + ')" aria-label="Cómo se calcula">i</button></span>';
                }
                trendQHtml = '<div class="trend-head">' +
                    '<h4 class="modal-section-title">Tendencia por trimestre</h4>' + sPromAnioHtml +
                    '</div><div class="trend-chips">' + sChips + '</div>';
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

            // Si NO hubo revisión en el trimestre seleccionado, no mostrar "0%" (rojo)
            var sinRevision = !s.fecha_supervision;
            var kpiHtml = sinRevision
                ? '<div class="modal-kpi"><span class="modal-kpi-value gray">—</span>' +
                  '<span class="modal-kpi-label">Sin revision en este trimestre</span></div>'
                : '<div class="modal-kpi">' +
                  '<span class="modal-kpi-value ' + colorClass + '">' + s.promedio + '%</span>' +
                  '<span class="modal-kpi-label">' + (currentTipo === 'operativas' ? 'Calificacion Operativa' : 'Calificacion Seguridad') + '</span>' +
                  '<span class="modal-kpi-date">' + s.fecha_supervision.split(' ')[0] + '</span>' +
                  '</div>';

            body.innerHTML = kpiHtml +
                infoHtml +
                '<div class="modal-stats">' +
                '<div class="modal-stat"><span class="stat-value">' + (s.supervisor || '-') + '</span><span class="stat-label">Supervisor</span></div>' +
                '<div class="modal-stat"><span class="stat-value">' + (sucInfo.grupo_nombre || '-') + '</span><span class="stat-label">Grupo</span></div>' +
                '</div>' +
                trendQHtml +
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
    // OpenStreetMap estándar: sin llave, sin marca de agua (CARTO exigía API key)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
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
                var eplCas = data.data.epl_cas || null;

                if (grupos.length === 0) {
                    container.innerHTML = '<div class="empty-state">No hay datos historicos</div>';
                    return;
                }

                var headerHtml = periodos.map(function(p) {
                    return '<div class="heatmap-period">' + ((p.nombre || '').substring(0, 12)) + '</div>';
                }).join('');

                // Helper: celdas de una entidad por cada periodo
                function rowCells(periodosData) {
                    return periodos.map(function(p) {
                        var pd = (periodosData && periodosData[p.nombre]) || {};
                        var val = pd.promedio;
                        var colorClass = pd.color || getColorClass(val);
                        var display = (val !== null && val !== undefined) ? val : '-';
                        return '<div class="heatmap-cell ' + colorClass + '">' + display + '</div>';
                    }).join('');
                }

                // 1) Fila "Promedio EPL CAS" SIEMPRE primero, resaltada
                var eplHtml = '';
                if (eplCas) {
                    eplHtml = '<div class="heatmap-row heatmap-total">' +
                        '<div class="heatmap-entity">Promedio EPL CAS</div>' +
                        rowCells(eplCas.periodos) +
                        '</div>';
                }

                // 2) Todos los grupos (sin límite), ya vienen ordenados mayor->menor
                var bodyHtml = grupos.map(function(g) {
                    return '<div class="heatmap-row">' +
                        '<div class="heatmap-entity">' + g.nombre + '</div>' +
                        rowCells(g.periodos) +
                        '</div>';
                }).join('');

                container.innerHTML = '<div class="heatmap-table">' +
                    '<div class="heatmap-header">' +
                    '<div class="heatmap-corner">Grupo</div>' +
                    headerHtml +
                    '</div>' +
                    '<div class="heatmap-body">' + eplHtml + bodyHtml + '</div>' +
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
                        warnContainer.innerHTML = '<div class="empty-state success-msg">Sin grupos en riesgo (70 a 79%)</div>';
                    }
                }
            } else {
                if (critContainer) critContainer.innerHTML = '<div class="error-state">No se pudieron cargar las alertas</div>';
                if (warnContainer) warnContainer.innerHTML = '';
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
