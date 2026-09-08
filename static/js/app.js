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
var currentTab = 'dashboard';      // dashboard | mapa | historico | alertas
var periodosDisponibles = [];
var periodoActivoId = null; // ID del periodo marcado como activo
var anioActual = null;      // Año del calendario en curso (de periodo-contexto)
var histAnio = null;        // Año que muestra la pestaña Histórico
var pendingPeriodoFromHash = null; // Periodo pedido en la URL, se valida al cargar el contexto
var map = null;
var markers = [];
var scrollPosition = 0; // Para guardar posición de scroll en iOS
var openModalsCount = 0; // Contador de modales abiertos

// Estado de agrupaciones expandidas/colapsadas
var agrupacionesEstado = {};

var TABS_VALIDAS = ['dashboard', 'mapa', 'historico', 'alertas'];
var NIVEL_TXT = { excellent: 'Excelente', good: 'Bueno', regular: 'Regular', critical: 'Crítico', gray: 'Sin datos' };

// ========== ESTADO EN LA URL (hash) ==========
// #p=<periodo_id|all>&t=<operativas|seguridad>&v=<tab>&r=<grupos|sucursales>
function parseHash() {
    var h = (window.location.hash || '').replace(/^#/, '');
    var out = {};
    h.split('&').forEach(function(kv) {
        if (!kv) return;
        var i = kv.indexOf('=');
        var k = i < 0 ? kv : kv.slice(0, i);
        var v = i < 0 ? '' : kv.slice(i + 1);
        try { v = decodeURIComponent(v); } catch (e) { /* hash malformado: se ignora */ }
        out[k] = v;
    });
    return out;
}

// Restaura tipo/tab/vista desde el hash ANTES de pedir datos. El periodo se
// deja pendiente: se valida contra periodosDisponibles en loadPeriodoContexto.
function applyHashState() {
    var st = parseHash();
    if (st.t === 'operativas' || st.t === 'seguridad') {
        currentTipo = st.t;
        document.querySelectorAll('.toggle-btn').forEach(function(b) {
            b.classList.toggle('active', b.dataset.tipo === currentTipo);
        });
    }
    if (st.r === 'grupos' || st.r === 'sucursales') {
        currentView = st.r;
        document.querySelectorAll('.sub-toggle[data-view]').forEach(function(b) {
            b.classList.toggle('active', b.dataset.view === currentView);
        });
        var title = document.getElementById('rankingTitle');
        if (title) title.textContent = currentView === 'grupos' ? 'de Grupos' : 'de Sucursales';
    }
    if (TABS_VALIDAS.indexOf(st.v) >= 0) {
        setActiveTab(st.v, false);
    }
    if (st.p) {
        pendingPeriodoFromHash = (st.p === 'all') ? 'all' : parseInt(st.p, 10);
        if (pendingPeriodoFromHash !== 'all' && isNaN(pendingPeriodoFromHash)) pendingPeriodoFromHash = null;
    }
}

function updateHash() {
    var parts = [];
    if (currentPeriodoId !== null && currentPeriodoId !== undefined) parts.push('p=' + currentPeriodoId);
    parts.push('t=' + currentTipo);
    parts.push('v=' + currentTab);
    parts.push('r=' + currentView);
    var newHash = '#' + parts.join('&');
    if (window.location.hash === newHash) return;
    lastAppHash = newHash; // hash escrito por la app: hashchange lo ignora
    try {
        // replaceState: no llena el historial (el gesto "atrás" sigue reservado a los modales)
        history.replaceState(history.state, '', newHash);
    } catch (e) {
        window.location.hash = newHash;
    }
}

// Deep link en una pestaña ya abierta (B4): si el hash cambia desde fuera de la app
// (usuario/enlace), se cierran los modales y se aplica el estado nuevo.
var lastAppHash = null;
window.addEventListener('hashchange', function() {
    if (window.location.hash === lastAppHash) return; // lo escribió la app
    if (openModalsCount) closeModalsAbove(0);
    applyHashState();
    loadPeriodoContexto();
});

// Activa una pestaña (UI). Si load=true carga su contenido.
// Al cambiar de pestaña se vuelve arriba: cada vista empieza por su título y contadores (M2).
function setActiveTab(tabId, load) {
    if (TABS_VALIDAS.indexOf(tabId) < 0) tabId = 'dashboard';
    var cambia = (tabId !== currentTab);
    currentTab = tabId;
    if (cambia) { try { window.scrollTo(0, 0); } catch (e) { /* ignorar */ } }
    document.querySelectorAll('.bottom-tab').forEach(function(b) {
        var on = b.dataset.tab === tabId;
        b.classList.toggle('active', on);
        if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    document.querySelectorAll('.tab-panel').forEach(function(p) {
        p.classList.toggle('active', p.id === tabId);
    });
    if (load) refreshActiveTab();
}

// Recarga SOLO la pestaña visible (mapa/histórico/alertas o dashboard)
function refreshActiveTab() {
    if (currentTab === 'mapa') {
        initMap();
        loadMapData();
    } else if (currentTab === 'historico') {
        loadHistorico();
    } else if (currentTab === 'alertas') {
        loadAlertas();
    } else {
        loadDashboard();
    }
}

// Recarga TODO lo visible: dashboard (KPIs + ranking) y, si aplica, la pestaña activa
function refreshAll() {
    loadDashboard();
    if (currentTab !== 'dashboard') refreshActiveTab();
}

// ========== FETCH CON ERRORES CLAROS ==========
// Devuelve el JSON del API; lanza si la red falla, el HTTP no es 2xx o success=false.
function fetchJson(url) {
    return fetch(url, { cache: 'no-store' }).then(function(res) {
        return res.json().catch(function() { return null; }).then(function(data) {
            if (!res.ok || !data || data.success === false) {
                var err = new Error((data && data.error) || ('HTTP ' + res.status));
                err.data = data;
                throw err;
            }
            return data;
        });
    });
}

var ERROR_MSG = 'No se pudieron cargar los datos.';
function errorHtml(retryId) {
    return '<div class="error-state" role="alert">' + ERROR_MSG +
        (retryId ? ' <button type="button" class="retry-btn" id="' + retryId + '">Reintentar</button>' : '') +
        '</div>';
}
function renderError(container, retryFn) {
    if (!container) return;
    var id = 'retry-' + Math.random().toString(36).slice(2, 8);
    container.innerHTML = errorHtml(id);
    var btn = document.getElementById(id);
    if (btn && retryFn) btn.addEventListener('click', retryFn);
}
function loadingHtml(txt) {
    return '<div class="loading" role="status" aria-live="polite">' + (txt || 'Cargando…') + '</div>';
}

// ========== HISTORIAL DE MODALES (gesto "atrás" del iPhone) ==========
// Cada modal abierto hace pushState({modal, id, depth}); popstate cierra los
// modales por encima de la profundidad del estado al que se regresó.
function pushModalState(kind, id) {
    try {
        history.pushState({ modal: kind, id: id, depth: openModalsCount }, '');
    } catch (e) { /* sin historial (p. ej. file://) */ }
}

function hideOverlay(ov) {
    if (ov) ov.classList.remove('active');
}

// Cierra los modales cuya profundidad sea mayor a `depth` (0 = ninguno abierto).
// El selector de periodo (sheet) cuenta como modal de profundidad 1 (A6).
function closeModalsAbove(depth) {
    var suc = document.getElementById('sucursalModalOverlay');
    var grp = document.getElementById('modalOverlay');
    var sheet = document.getElementById('periodSheetOverlay');
    var guard = 0;
    while (openModalsCount > depth && guard++ < 5) {
        if (sheet && sheet.classList.contains('active')) {
            hideOverlay(sheet);
            var sel = document.getElementById('periodSelector');
            if (sel) sel.classList.remove('open');
            unlockBodyScroll();
        } else if (suc && suc.classList.contains('active')) {
            hideOverlay(suc);
            unlockBodyScroll();
        } else if (grp && grp.classList.contains('active')) {
            hideOverlay(grp);
            unlockBodyScroll();
        } else {
            // Contador desfasado: normalizar
            openModalsCount = depth;
            if (depth <= 0) unlockBodyScroll();
            break;
        }
    }
}

// Cierra el modal superior. Usa history.back() SOLO si el estado actual del
// historial es el de ese modal (evita saltos fuera de la página).
function closeTopModal() {
    if (openModalsCount <= 0) return;
    var st = history.state;
    if (st && st.modal && st.depth === openModalsCount) {
        history.back(); // popstate → closeModalsAbove(depth-1)
    } else {
        closeModalsAbove(openModalsCount - 1);
    }
}

// Acción diferida hasta que el historial cierre la sheet (selección de periodo)
var afterSheetClose = null;

window.addEventListener('popstate', function(e) {
    var st = e.state;
    var depth = (st && st.modal) ? (st.depth || 0) : 0;
    closeModalsAbove(depth);
    if (afterSheetClose) {
        var fn = afterSheetClose;
        afterSheetClose = null;
        fn();
    }
});

// ========== iOS MODAL FIX ==========
// Foco (M13): al abrir el primer modal se guarda el elemento activo y el fondo queda
// inerte; al cerrar el último se restaura el foco donde estaba.
var focusAntesDeModal = null;
function lockBodyScroll() {
    if (openModalsCount === 0) {
        scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
        document.body.classList.add('modal-open');
        document.body.style.top = -scrollPosition + 'px';
        focusAntesDeModal = document.activeElement;
        var app = document.querySelector('.app-container');
        if (app) app.setAttribute('inert', '');
        var nav = document.querySelector('.bottom-nav');
        if (nav) nav.setAttribute('inert', '');
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
        var app = document.querySelector('.app-container');
        if (app) app.removeAttribute('inert');
        var nav = document.querySelector('.bottom-nav');
        if (nav) nav.removeAttribute('inert');
        if (focusAntesDeModal && focusAntesDeModal.focus && document.contains(focusAntesDeModal)) {
            try { focusAntesDeModal.focus({ preventScroll: true }); } catch (e) { /* ignorar */ }
        }
        focusAntesDeModal = null;
    }
}

// Mueve el foco al contenedor del modal (tabindex=-1) para lectores de pantalla/teclado
function focusModal(overlay) {
    var c = overlay ? overlay.querySelector('.modal-container') : null;
    if (!c) return;
    c.setAttribute('tabindex', '-1');
    try { c.focus({ preventScroll: true }); } catch (e) { /* ignorar */ }
}

// Escape cierra lo que esté encima: popup ⓘ → modal/sheet superior
document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    var popup = document.querySelector('.info-popup-overlay');
    if (popup) { popup.remove(); return; }
    if (openModalsCount > 0) { e.preventDefault(); closeTopModal(); }
});

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
    ov.innerHTML = '<div class="info-popup" role="dialog" aria-modal="true" aria-label="' + escAttr(String(title).replace(/<[^>]+>/g, '')) + '">' +
        '<div class="info-popup-head"><span>' + title + '</span>' +
        '<button type="button" class="info-popup-close" aria-label="Cerrar">&times;</button></div>' +
        '<div class="info-popup-body">' + html + '</div></div>';
    document.body.appendChild(ov);
    var abridor = document.activeElement;
    function close() {
        if (ov.parentNode) ov.parentNode.removeChild(ov);
        if (abridor && abridor.focus && document.contains(abridor)) { try { abridor.focus({ preventScroll: true }); } catch (e) { /* ignorar */ } }
    }
    ov.addEventListener('click', function(e) { if (e.target === ov) close(); });
    var closeBtn = ov.querySelector('.info-popup-close');
    closeBtn.addEventListener('click', close);
    try { closeBtn.focus({ preventScroll: true }); } catch (e) { /* ignorar */ }
}

// Explica cómo se calcula el "Año N" (promedio de los trimestres del año) según el contexto
function showAcumuladoInfo(scope, anio) {
    var como;
    if (scope === 'sucursal') {
        como = 'Es el <strong>promedio</strong> de las calificaciones de esta sucursal en los trimestres del año ' + anio + ' (una supervisión por trimestre).';
    } else if (scope === 'grupo') {
        como = 'Es el <strong>promedio</strong> de las calificaciones de las sucursales del grupo durante los trimestres del año ' + anio + '. Cada sucursal pesa igual.';
    } else {
        como = 'Es el <strong>promedio</strong> de las calificaciones de los trimestres del año ' + anio + '. Cada sucursal pesa igual.';
    }
    showInfoPopup('¿Cómo se calcula el Año ' + anio + '?',
        como + '<br><br>Solo cuenta lo de <strong>' + anio + '</strong> — no incluye años anteriores. Se reinicia cada 1 de enero.');
}

// UN solo término para el concepto anual en toda la UI: "Año 2026"
function anioLabelTxt() {
    return anioActual ? ('Año ' + anioActual) : 'Año en curso';
}

// "Q3 2026" (nombre con espacio) para un periodo de la lista
function periodoNombre(p) {
    if (!p) return '';
    return String(p.nombre || p.codigo || '').replace('-', ' ');
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

// Altura real del header sticky → --header-h (el encabezado y la fila PROMEDIO del
// histórico se fijan justo debajo; el alto cambia con el safe-area del iPhone)
function updateHeaderHeight() {
    var h = document.querySelector('.header');
    if (h) document.documentElement.style.setProperty('--header-h', h.offsetHeight + 'px');
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    initTheme();
    initToggles();
    initTabs();
    initPeriodSelector();
    initHistoricoControls();
    updateHeaderHeight();
    window.addEventListener('resize', updateHeaderHeight);
    window.addEventListener('orientationchange', function() { setTimeout(updateHeaderHeight, 100); });
    // Un estado de modal viejo (recarga con modal abierto) no debe capturar "atrás"
    try {
        if (history.state && history.state.modal) history.replaceState(null, '', window.location.href);
    } catch (e) { /* ignorar */ }
    applyHashState();      // Restaurar tipo/tab/vista/periodo desde la URL ANTES de pedir datos
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

    var cancelBtn = document.getElementById('periodSheetClose');
    if (cancelBtn) cancelBtn.addEventListener('click', function() { closePeriodSheet(); });
}

function loadPeriodoContexto() {
    var periodName = document.getElementById('periodName');
    if (periodName) periodName.textContent = 'Cargando…';

    fetchJson('/api/periodo-contexto/' + currentTipo)
        .then(function(data) {
            var d = data.data || {};

            // Guardar periodo activo (el "en curso")
            if (d.periodo_actual) {
                currentPeriodo = d.periodo_actual;
                currentPeriodoId = d.periodo_actual.id;
                periodoActivoId = d.periodo_actual.id;
                if (d.periodo_actual.fecha_inicio) anioActual = parseInt(String(d.periodo_actual.fecha_inicio).slice(0, 4), 10) || null;
            }

            // Guardar lista de periodos con info de activo
            periodosDisponibles = (d.periodos || []).map(function(p) {
                p.activo = (periodoActivoId && p.id == periodoActivoId);
                return p;
            });
            if (!anioActual && periodosDisponibles.length && periodosDisponibles[0].fecha_inicio) {
                anioActual = parseInt(String(periodosDisponibles[0].fecha_inicio).slice(0, 4), 10) || null;
            }
            if (!histAnio) histAnio = anioActual;

            // Periodo pedido en la URL: solo si existe en la lista y no es futuro; si no, el activo
            if (pendingPeriodoFromHash !== null) {
                if (pendingPeriodoFromHash === 'all') {
                    currentPeriodoId = 'all';
                    currentPeriodo = null;
                } else {
                    var pf = periodosDisponibles.find(function(p) { return p.id == pendingPeriodoFromHash; });
                    if (pf && !(pf.futuro && !pf.activo)) {
                        currentPeriodoId = pf.id;
                        currentPeriodo = pf;
                    }
                }
                pendingPeriodoFromHash = null;
            }

            if (periodName) {
                periodName.textContent = (currentPeriodoId === 'all')
                    ? anioLabelTxt()
                    : (periodoNombre(currentPeriodo) || '—');
            }

            // Actualizar progreso (loadKPIs lo vuelve a fijar con el periodo seleccionado)
            if (d.progreso) {
                var progressText = document.getElementById('progressText');
                if (progressText) {
                    progressText.textContent = d.progreso.supervisadas + '/' + d.progreso.total;
                }
            }

            updateHash();
            refreshAll();
        })
        .catch(function(e) {
            console.error('Error loading periodo contexto:', e);
            if (periodName) periodName.textContent = 'Sin conexión';
            pendingPeriodoFromHash = null;
            refreshAll(); // Cargar lo visible aunque falle (mostrará su propio error)
        });
}

function openPeriodSheet() {
    var overlay = document.getElementById('periodSheetOverlay');
    var body = document.getElementById('periodSheetBody');
    var selector = document.getElementById('periodSelector');

    if (!overlay || !body) return;

    // Generar opciones - empezar con "Todos"
    var html = '';

    // Opción "Año N" = promedio de los trimestres del año en curso
    var isAllSelected = currentPeriodoId === 'all';
    html += '<div class="period-option ' + (isAllSelected ? 'selected' : '') + '" data-id="all">' +
        '<div class="period-option-info">' +
            '<span class="period-option-name">' + anioLabelTxt() + '</span>' +
            '<span class="period-option-dates">Promedio de los trimestres del año</span>' +
        '</div>' +
        '<div class="period-option-check">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">' +
                '<polyline points="20 6 9 17 4 12"/>' +
            '</svg>' +
        '</div>' +
    '</div>';

    // Separador
    html += '<div class="period-separator"></div>';

    // Periodos individuales, Q1 → Q4 (mismo orden que los chips)
    var ordenados = periodosDisponibles.slice().sort(function(a, b) {
        return String(a.fecha_inicio || '').localeCompare(String(b.fecha_inicio || ''));
    });
    ordenados.forEach(function(p) {
        var isSelected = currentPeriodoId && currentPeriodoId == p.id;
        var fechas = formatPeriodDates(p.fecha_inicio, p.fecha_fin);
        var isActivo = p.activo || (periodoActivoId && p.id == periodoActivoId);
        var isFuturo = !!p.futuro && !isActivo;

        html += '<div class="period-option ' + (isSelected ? 'selected' : '') + (isFuturo ? ' disabled' : '') + '" data-id="' + p.id + '"' + (isFuturo ? ' aria-disabled="true"' : '') + '>' +
            '<div class="period-option-info">' +
                '<span class="period-option-name">' + periodoNombre(p) +
                    (isActivo ? ' <span class="period-activo-badge">En curso</span>' : '') +
                    (isFuturo ? ' <span class="period-futuro-badge">Próximo</span>' : '') +
                '</span>' +
                '<span class="period-option-dates">' + fechas + (isFuturo ? ' · disponible al iniciar el trimestre' : '') + '</span>' +
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
    // El gesto "atrás" cierra la sheet en vez de salir del dashboard (A6)
    pushModalState('sheet', 'periodo');
    var cancelBtn = document.getElementById('periodSheetClose');
    if (cancelBtn) { try { cancelBtn.focus({ preventScroll: true }); } catch (e) { /* ignorar */ } }
}

// Cierra la sheet por el historial (si su estado es el actual) y ejecuta `cb`
// DESPUÉS de que el historial regresó, para que updateHash escriba en la entrada correcta.
function closePeriodSheet(cb) {
    var overlay = document.getElementById('periodSheetOverlay');
    if (!overlay || !overlay.classList.contains('active')) {
        if (cb) cb();
        return;
    }
    var st = history.state;
    if (st && st.modal === 'sheet' && st.depth === openModalsCount) {
        afterSheetClose = cb || null;
        history.back(); // popstate → closeModalsAbove → afterSheetClose()
    } else {
        closeModalsAbove(openModalsCount - 1);
        if (cb) cb();
    }
}

function selectPeriodo(periodoId) {
    var periodo = null;
    if (periodoId !== 'all') {
        periodo = periodosDisponibles.find(function(p) { return p.id == periodoId; });
        if (!periodo) return;
    }

    closePeriodSheet(function() {
        var periodName = document.getElementById('periodName');
        if (periodoId === 'all') {
            // "Año N" = promedio de los trimestres del año
            currentPeriodoId = 'all';
            currentPeriodo = null;
            if (periodName) periodName.textContent = anioLabelTxt();
        } else {
            currentPeriodoId = periodo.id;
            currentPeriodo = periodo;
            if (periodName) periodName.textContent = periodoNombre(periodo);
        }
        // Recargar todo lo visible con el nuevo periodo (dashboard + mapa/histórico/alertas si están abiertos)
        updateHash();
        refreshAll();
        loadPeriodoProgreso();
    });
}

function loadPeriodoProgreso() {
    // Recargar progreso del periodo seleccionado
    var url = '/api/periodo-contexto/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId; // el API acepta 'all' (avance del año)
    }
    fetchJson(url)
        .then(function(data) {
            if (data.data && data.data.progreso) {
                var progressText = document.getElementById('progressText');
                if (progressText) {
                    progressText.textContent = data.data.progreso.supervisadas + '/' + data.data.progreso.total;
                }
            }
        })
        .catch(function(e) { console.error('Error loading progreso:', e); });
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
            if (btn.dataset.tipo === currentTipo) return;
            document.querySelectorAll('.toggle-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentTipo = btn.dataset.tipo;
            // CONSERVA el periodo seleccionado (no vuelve al activo) y recarga todo lo visible
            updateHash();
            refreshAll();
            loadPeriodoProgreso();
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
            updateHash();
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
            var tabId = btn.dataset.tab;
            setActiveTab(tabId, false);
            updateHash();
            // El dashboard ya está cargado; las demás pestañas se cargan al entrar
            if (tabId !== 'dashboard') refreshActiveTab();
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

var MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

// Acepta "2026-08-11" (ISO) o "11/08/2026" (dd/mm/aaaa) → [aaaa, mm, dd] o null
function partesFecha(s) {
    if (!s) return null;
    var t = String(s).split(' ')[0];
    var p;
    if (t.indexOf('/') >= 0) { p = t.split('/'); if (p.length < 3) return null; return [p[2], p[1], p[0]]; }
    p = t.split('-');
    if (p.length < 3) return null;
    return [p[0], p[1], p[2]];
}

// "2026-08-11" → "11 ago 2026" (formato "d mmm aaaa" en todo el producto)
function fmtFecha(iso) {
    var p = partesFecha(iso);
    if (!p) return iso || '';
    return parseInt(p[2], 10) + ' ' + MESES_CORTOS[parseInt(p[1], 10) - 1] + ' ' + p[0];
}

// "2026-08-11" → "11 ago 26" (barras de tendencia: siempre con año, en corto)
function fmtFechaCorta(iso) {
    var p = partesFecha(iso);
    if (!p) return iso || '';
    return parseInt(p[2], 10) + ' ' + MESES_CORTOS[parseInt(p[1], 10) - 1] + ' ' + String(p[0]).slice(2);
}

// Posición por competencia (1, 1, 3): mismo valor mostrado = misma posición
function rankingPosiciones(valores) {
    var out = [], pos = 1;
    for (var i = 0; i < valores.length; i++) {
        if (i > 0 && fmt1(valores[i]) !== fmt1(valores[i - 1])) pos = i + 1;
        out.push(pos);
    }
    return out;
}

// Medalla oro/plata/bronce SOLO en el ranking principal y solo si ≤3 filas comparten el puesto (A1)
var rankingPosCounts = null;
function medalClass(pos) {
    if (!pos || pos > 3) return '';
    if (rankingPosCounts && rankingPosCounts[pos] > 3) return '';
    return 'pos-' + pos;
}
function contarPosiciones(items) {
    var c = {};
    (items || []).forEach(function(it) {
        var p = it && it.posicion;
        if (p) c[p] = (c[p] || 0) + 1;
    });
    return c;
}

function loadKPIs() {
    var url = '/api/kpis/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }
    var el = function(id) { return document.getElementById(id); };
    if (el('kpiSub')) el('kpiSub').textContent = 'Cargando…';

    fetchJson(url)
        .then(function(data) {
            var d = data.data;
            var esAnio = (currentPeriodoId === 'all');
            var tipoTxt = (currentTipo === 'operativas') ? 'Operativa' : 'de Seguridad';
            var periodoTxt = esAnio
                ? ('Año ' + d.anio)
                : (periodoNombre(currentPeriodo) || 'Trimestre');
            var tiene = (d.promedio !== null && d.promedio !== undefined);
            var faltan = (d.total_sucursales || 0) - (d.sucursales_supervisadas || 0);
            var trimestres = d.trimestres || [];
            // El año está "en curso" mientras haya un trimestre en curso (no se dice "preliminar")
            var anioEnCurso = trimestres.some(function(q) { return q.en_curso; });
            var ultimoQ = trimestres.filter(function(q) { return q.promedio !== null && q.promedio !== undefined; }).pop();
            var hastaTxt = ultimoQ ? ((ultimoQ.codigo || '').split('-')[0] || ultimoQ.nombre) : '';

            // 1) Tarjeta principal: qué mide · de qué periodo · sobre cuántas
            if (el('kpiPromedioLabel')) {
                el('kpiPromedioLabel').innerHTML = 'Calificación ' + tipoTxt + ' · ' + periodoTxt +
                    ((d.en_curso || (esAnio && anioEnCurso)) ? ' <span class="pill pill-curso">En curso</span>' : '');
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

            // 2) Tendencia: siempre con signo (el pill "En curso" ya avisa que puede moverse)
            var trendEl = el('kpiTrend');
            if (trendEl) {
                var t = (!esAnio) ? d.tendencia : null;
                if (t && t.direccion) {
                    var arrow = t.direccion === 'up' ? '▲' : (t.direccion === 'down' ? '▼' : '≈');
                    trendEl.className = 'kpi-trend ' + t.direccion;
                    trendEl.innerHTML = arrow + ' ' + (t.delta > 0 ? '+' : '') + fmt1(t.delta) +
                        ' <span class="trend-vs">vs ' + t.vs + ' ' + d.anio + (t.prev !== undefined ? ' (' + fmt1(t.prev) + ')' : '') + '</span>';
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
                    var selQ = (!esAnio && currentPeriodoId == q.id);
                    return '<div class="' + cls + '" role="button" tabindex="0" ' + (q.futuro ? 'aria-disabled="true"' : 'onclick="selectPeriodo(' + q.id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();selectPeriodo(' + q.id + ')}"') +
                        ' aria-pressed="' + (selQ ? 'true' : 'false') + '" aria-label="' + qLbl + ' ' + d.anio + (q.en_curso ? ', en curso' : '') + (q.futuro ? ', próximo' : '') + '"><b class="' + vcls + '">' + val + '</b><span>' + qLbl + ' · ' + sub + '</span></div>';
                }).join('');
            }

            // 4) Año N (en curso hasta cerrar Q4) y Año N-1 (cerrado, referencia)
            // En modo año la tarjeta "Año N" es la seleccionada (el chip Q3 no lleva acento); tocarla selecciona el año
            var anioCard = el('kpiAnio') ? el('kpiAnio').closest('.kpi-card') : null;
            if (anioCard) {
                anioCard.classList.toggle('sel', esAnio);
                anioCard.classList.add('clickable');
                anioCard.setAttribute('role', 'button');
                anioCard.setAttribute('tabindex', '0');
                anioCard.setAttribute('aria-pressed', esAnio ? 'true' : 'false');
                anioCard.setAttribute('aria-label', 'Año ' + d.anio + ', ' + fmt1(d.promedio_acumulado) + ', ' + nivelTxt(getColorClass(d.promedio_acumulado)));
                anioCard.onclick = function() { if (!esAnio) selectPeriodo('all'); };
                anioCard.onkeydown = function(ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); if (!esAnio) selectPeriodo('all'); } };
            }
            if (el('kpiAnioLabel')) el('kpiAnioLabel').textContent = 'Año ' + d.anio;
            if (el('kpiAnio')) {
                el('kpiAnio').textContent = fmt1(d.promedio_acumulado);
                el('kpiAnio').className = 'kpi-value mid ' + getColorClass(d.promedio_acumulado);
            }
            if (el('kpiAnioSub')) el('kpiAnioSub').textContent = (d.sucursales_anio || 0) + ' sucursales' + (hastaTxt ? ' · hasta ' + hastaTxt : '');
            if (el('kpiPrevLabel')) el('kpiPrevLabel').textContent = 'Año ' + d.anio_anterior;
            var hayPrev = (d.promedio_anio_anterior !== null && d.promedio_anio_anterior !== undefined);
            if (el('kpiPrev')) el('kpiPrev').textContent = hayPrev ? fmt1(d.promedio_anio_anterior) : '—';
            if (el('kpiPrevSub')) el('kpiPrevSub').textContent = hayPrev ? ((d.sucursales_anio_anterior || 0) + ' sucursales · año cerrado') : 'Sin datos';
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

            // 6) Fecha de corte de los datos (sin nombrar al proveedor de captura)
            if (el('dataCut')) {
                el('dataCut').textContent = (d.fecha_corte ? 'Datos al ' + fmtFecha(d.fecha_corte) : '') +
                    (hayPrev ? (d.fecha_corte ? ' · ' : '') + d.anio_anterior + ' no es comparable trimestre a trimestre (otro calendario)' : '');
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
            if (el('kpiSub')) {
                el('kpiSub').innerHTML = ERROR_MSG + ' <button type="button" class="retry-btn retry-inline" onclick="loadKPIs()">Reintentar</button>';
            }
            if (el('qChips')) el('qChips').innerHTML = '';
            var dist = el('distributionBars');
            if (dist) renderError(dist, loadKPIs);
        });
}

function renderDistribution(dist) {
    var container = document.getElementById('distributionBars');
    if (!container) return;

    var total = (dist.excelente || 0) + (dist.bueno || 0) + (dist.regular || 0) + (dist.critico || 0);

    if (total === 0) {
        container.innerHTML = '<div class="empty-state">Sin sucursales supervisadas en este periodo</div>';
        return;
    }

    // Semáforo con texto además de color (accesible sin depender del color)
    var items = [
        { label: 'Excelente', rango: '≥90', count: dist.excelente || 0, cls: 'excellent' },
        { label: 'Bueno', rango: '80–89', count: dist.bueno || 0, cls: 'good' },
        { label: 'Regular', rango: '70–79', count: dist.regular || 0, cls: 'regular' },
        { label: 'Crítico', rango: '<70', count: dist.critico || 0, cls: 'critical' }
    ];

    var html = items.map(function(item) {
        var pct = Math.round((item.count / total) * 100);
        return '<div class="dist-bar" role="group" aria-label="' + item.label + ' ' + item.rango + ': ' + item.count + ' sucursales (' + pct + '%)">' +
            '<div class="dist-label">' +
            '<span class="dist-name ' + item.cls + '">' + item.label + ' <small class="dist-range">' + item.rango + '</small></span>' +
            '<span class="dist-count">' + item.count + ' (' + pct + '%)</span>' +
            '</div>' +
            '<div class="dist-track" aria-hidden="true">' +
            '<div class="dist-fill ' + item.cls + '" style="width: ' + pct + '%"></div>' +
            '</div>' +
            '</div>';
    }).join('');

    container.innerHTML = html + '<div class="dist-legend">' + total + ' sucursales supervisadas · Excelente ≥90 · Bueno 80–89 · Regular 70–79 · Crítico &lt;70</div>';
}

// ========== RANKING ==========
function loadRanking() {
    var container = document.getElementById('rankingList');
    if (!container) return;
    container.innerHTML = loadingHtml();

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

    fetchJson(endpoint)
        .then(function(data) {
            var items = data.data || [];
            if (items.length === 0) {
                container.innerHTML = '<div class="empty-state">Sin resultados para este filtro</div>';
                return;
            }

            var html = '';
            // Medallas: solo en este ranking y solo si el puesto no está masivamente empatado
            rankingPosCounts = contarPosiciones(items);

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
                // Vista de sucursales
                var esAnio = (currentPeriodoId === 'all');
                html = items.map(function(item) {
                    var pos = item.posicion;
                    var isPendiente = pos === null;
                    var posClass = medalClass(pos);
                    var colorClass = item.color || 'gray';
                    var promedio = item.promedio !== null ? fmt1(item.promedio) : 'Pendiente';
                    var meta = (item.grupo_nombre || '—');
                    if (esAnio && item.total_supervisiones) {
                        meta += ' · ' + item.total_supervisiones + ' trimestre' + (item.total_supervisiones === 1 ? '' : 's');
                    }
                    var aria = item.nombre + ', ' + (item.promedio !== null ? fmt1(item.promedio) + ', ' + nivelTxt(colorClass) : 'pendiente de supervisar');

                    return '<div class="ranking-item ' + (isPendiente ? 'pendiente' : '') + '" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" onclick="openSucursalModal(' + item.id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSucursalModal(' + item.id + ')}">' +
                        '<span class="ranking-pos ' + posClass + '">' + (pos || '–') + '</span>' +
                        '<div class="ranking-info">' +
                        '<span class="ranking-name" title="' + escAttr(item.nombre) + '">' + item.nombre + '</span>' +
                        '<span class="ranking-meta">' + meta + '</span>' +
                        '</div>' +
                        '<span class="ranking-score ' + colorClass + '">' + promedio + '</span>' +
                        '</div>';
                }).join('');
            }

            container.innerHTML = html;
        })
        .catch(function(e) {
            console.error('Error loading ranking:', e);
            renderError(container, loadRanking);
        });
}

function nivelTxt(colorClass) {
    return NIVEL_TXT[colorClass] || NIVEL_TXT.gray;
}

function escAttr(s) {
    return String(s === null || s === undefined ? '' : s)
        .replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Meta "N de M sucursales · faltan K" para un grupo del ranking ("parcial" va como tag junto a la cifra)
function coberturaTxt(evaluadas, activas) {
    var ev = (evaluadas === null || evaluadas === undefined) ? 0 : evaluadas;
    var ac = (activas === null || activas === undefined) ? 0 : activas;
    var txt = ev + ' de ' + ac + ' sucursal' + (ac === 1 ? '' : 'es');
    if (ev > 0 && ev < ac) txt += ' · faltan ' + (ac - ev);
    return txt;
}

// Tag "PARCIAL · 1/4" bajo la cifra de un grupo con sucursales sin supervisar
function partialTag(evaluadas, activas) {
    return '<small class="partial-tag">Parcial · ' + (evaluadas || 0) + '/' + (activas || 0) + '</small>';
}

// Renderiza una fila de grupo (ranking principal o dentro de PLOG).
// Medalla solo en el ranking principal; dentro de PLOG el disco es neutro (A1/B9).
function renderGrupoRow(g, pos, extraClass) {
    var isPendiente = (g.promedio === null || g.promedio === undefined);
    var esSubfila = extraClass === 'agrupacion-child';
    var posClass = (esSubfila || isPendiente) ? '' : medalClass(pos);
    var colorClass = isPendiente ? 'gray' : (g.color || getColorClass(g.promedio));
    var evaluadas = (g.evaluadas !== undefined) ? g.evaluadas : g.total_supervisiones;
    var activas = (g.activas !== undefined) ? g.activas : g.total_sucursales;
    var parcial = !isPendiente && evaluadas < activas;
    var promedio = isPendiente ? 'Pendiente' : fmt1(g.promedio);
    var meta = coberturaTxt(evaluadas, activas) + ' · ' + territorioTxt(g.territorio);
    var aria = g.nombre + ', ' + (isPendiente ? 'sin supervisión' : fmt1(g.promedio) + ', ' + nivelTxt(colorClass) + (parcial ? ', parcial' : '')) + ', ' + coberturaTxt(evaluadas, activas);

    return '<div class="ranking-item ' + (extraClass || '') + (isPendiente ? ' pendiente' : '') + '" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" onclick="openGrupoModal(' + g.id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openGrupoModal(' + g.id + ')}">' +
        '<span class="ranking-pos ' + posClass + '">' + ((isPendiente || !pos) ? '–' : pos) + '</span>' +
        '<div class="ranking-info">' +
        '<span class="ranking-name" title="' + escAttr(g.nombre) + '">' + g.nombre + '</span>' +
        '<span class="ranking-meta">' + meta + '</span>' +
        '</div>' +
        '<span class="ranking-score ' + colorClass + (parcial ? ' partial' : '') + '">' + promedio +
            (parcial ? partialTag(evaluadas, activas) : '') + '</span>' +
        '</div>';
}

function territorioTxt(t) {
    if (t === 'local') return 'Local';
    if (t === 'foranea') return 'Foránea';
    if (t === 'mixto') return 'Mixto';
    return t || '';
}

// Renderiza un grupo individual
function renderGrupoItem(item) {
    return renderGrupoRow(item, item.posicion, '');
}

// Renderiza una agrupación (PLOG) con sus grupos anidados
function renderAgrupacion(agrupacion) {
    var isExpanded = agrupacionesEstado[agrupacion.id] === true;
    var isPendiente = (agrupacion.promedio === null || agrupacion.promedio === undefined);
    var colorClass = isPendiente ? 'gray' : (agrupacion.color || 'gray');
    var evaluadas = agrupacion.total_supervisiones || 0; // nº de sucursales evaluadas en la agrupación
    var activas = agrupacion.total_sucursales || 0;
    var parcial = !isPendiente && evaluadas < activas;
    var promedio = isPendiente ? 'Pendiente' : fmt1(agrupacion.promedio);
    var pos = agrupacion.posicion;
    var posClass = isPendiente ? '' : medalClass(pos);

    // Renderizar grupos dentro de la agrupación (misma fila que el ranking principal)
    var gruposHtml = '';
    if (agrupacion.grupos && agrupacion.grupos.length > 0) {
        gruposHtml = agrupacion.grupos.map(function(g) {
            return renderGrupoRow(g, g.posicion_interna, 'agrupacion-child');
        }).join('');
    }
    var aria = agrupacion.nombre + ', ' + (isPendiente ? 'sin supervisión' : fmt1(agrupacion.promedio) + ', ' + nivelTxt(colorClass)) +
        ', ' + agrupacion.total_grupos + ' grupos, ' + coberturaTxt(evaluadas, activas) + (isExpanded ? ', expandido' : ', contraído');

    return '<div class="agrupacion-item ' + (isExpanded ? 'expanded' : '') + '" data-agrupacion="' + agrupacion.id + '">' +
        '<div class="agrupacion-header" role="button" tabindex="0" aria-expanded="' + (isExpanded ? 'true' : 'false') + '" aria-label="' + escAttr(aria) + '" onclick="toggleAgrupacion(\'' + agrupacion.id + '\')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();toggleAgrupacion(\'' + agrupacion.id + '\')}">' +
            '<span class="ranking-pos ' + posClass + '">' + ((isPendiente || !pos) ? '–' : pos) + '</span>' +
            '<svg class="agrupacion-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
                '<polyline points="9 6 15 12 9 18"/>' +
            '</svg>' +
            '<div class="ranking-info">' +
                '<span class="ranking-name" title="' + escAttr(agrupacion.nombre) + '">' + agrupacion.nombre + '</span>' +
                '<span class="ranking-meta">' + agrupacion.total_grupos + ' grupos · ' + coberturaTxt(evaluadas, activas) + '</span>' +
            '</div>' +
            '<span class="ranking-score ' + colorClass + (parcial ? ' partial' : '') + '">' + promedio +
                (parcial ? partialTag(evaluadas, activas) : '') + '</span>' +
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
        var head = element.querySelector('.agrupacion-header');
        if (head) head.setAttribute('aria-expanded', element.classList.contains('expanded') ? 'true' : 'false');
    }
}

// ========== MODALS ==========
function periodoLabelTxt() {
    // "Q3 2026" | "Año 2026"
    if (currentPeriodoId === 'all') return anioLabelTxt();
    return periodoNombre(currentPeriodo) || 'Trimestre';
}

function tipoLabelTxt() {
    return currentTipo === 'operativas' ? 'Operativa' : 'de Seguridad';
}

// Chips Q1..Q4 con flecha (compartido por modal de grupo y de sucursal)
function renderTrendChips(tendencia) {
    return tendencia.map(function(t) {
        var qLabel = (t.codigo || '').split('-')[0];
        var score = t.tiene_dato ? fmt1(t.promedio) : '—';
        var arrow = '';
        if (t.direccion === 'up') arrow = '<span class="trend-arrow up" aria-label="sube">▲</span>';
        else if (t.direccion === 'down') arrow = '<span class="trend-arrow down" aria-label="baja">▼</span>';
        else if (t.direccion === 'flat') arrow = '<span class="trend-arrow flat" aria-label="estable">▬</span>';
        var deltaTxt = (t.delta !== null && t.delta !== undefined) ? ((t.delta > 0 ? '+' : '') + fmt1(t.delta)) : '';
        var cls = t.tiene_dato ? t.color : 'off';
        var title = (t.nombre || '') + (t.tiene_dato ? ' · ' + fmt1(t.promedio) + ' · ' + nivelTxt(t.color) : ' · sin datos') +
            (deltaTxt ? ' · ' + deltaTxt + ' vs trimestre anterior' : '');
        return '<div class="trend-chip ' + cls + '" title="' + escAttr(title) + '" aria-label="' + escAttr(title) + '">' +
            '<span class="trend-q">' + qLabel + '</span>' +
            '<span class="trend-score">' + score + '</span>' + arrow +
            '</div>';
    }).join('');
}

function openGrupoModal(grupoId) {
    var overlay = document.getElementById('modalOverlay');
    var body = document.getElementById('modalBody');
    var title = document.getElementById('modalTitle');
    var container = overlay ? overlay.querySelector('.modal-container') : null;

    if (!overlay || !body) return;

    var yaAbierto = overlay.classList.contains('active');
    if (!yaAbierto) {
        // iOS fix: bloquear scroll del body
        lockBodyScroll();
        // El gesto "atrás" cierra el modal en vez de salir de la página
        pushModalState('grupo', grupoId);
    }

    if (title) title.textContent = 'Grupo';
    body.innerHTML = loadingHtml();
    body.scrollTop = 0;
    overlay.classList.add('active');

    // Forzar repaint para iOS
    forceRepaint(container);
    focusModal(overlay);

    // Pasar el trimestre seleccionado para que el drill-down COINCIDA con el
    // ranking y el mapa (antes mostraba el histórico de todos los años).
    var grupoUrl = '/api/grupo/' + grupoId + '/' + currentTipo;
    if (currentPeriodoId) grupoUrl += '?periodo_id=' + currentPeriodoId;

    fetchJson(grupoUrl)
        .then(function(data) {
            var g = data.data;
            if (title) title.textContent = g.grupo ? g.grupo.nombre : 'Grupo';

            var colorClass = g.color || getColorClass(g.promedio);
            var esAnio = (currentPeriodoId === 'all');

            // Sucursales del grupo (A1): posición SOLO entre las que tienen supervisión
            // (competencia 1,1,3), disco neutro sin medalla; pendientes al final con "–".
            function esPendienteSuc(s) { return !s.supervisiones || s.promedio === null || s.promedio === undefined; }
            var sucConDato = (g.sucursales || []).filter(function(s) { return !esPendienteSuc(s); })
                .sort(function(a, b) { return b.promedio - a.promedio; });
            var sucPendientes = (g.sucursales || []).filter(esPendienteSuc);
            var posiciones = rankingPosiciones(sucConDato.map(function(s) { return s.promedio; }));

            function filaSucursal(s, pos) {
                var pendiente = esPendienteSuc(s);
                var sColorClass = pendiente ? 'gray' : (s.color || getColorClass(s.promedio));
                var scoreTxt = pendiente ? '—' : fmt1(s.promedio);
                var n = s.supervisiones || 0;
                var metaTxt = pendiente
                    ? ('Sin supervisión en ' + periodoLabelTxt())
                    : (n + ' supervisi' + (n === 1 ? 'ón' : 'ones'));
                var aria = s.nombre + ', ' + (pendiente ? 'pendiente de supervisar' : 'posición ' + pos + ', ' + fmt1(s.promedio) + ', ' + nivelTxt(sColorClass));
                return '<div class="modal-list-item' + (pendiente ? ' pendiente' : '') + '" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" onclick="openSucursalModal(' + s.id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSucursalModal(' + s.id + ')}">' +
                    '<span class="ranking-pos">' + (pendiente ? '–' : pos) + '</span>' +
                    '<div class="ranking-info">' +
                    '<span class="ranking-name" title="' + escAttr(s.nombre) + '">' + s.nombre + '</span>' +
                    '<span class="ranking-meta">' + metaTxt + '</span>' +
                    '</div>' +
                    '<span class="ranking-score ' + sColorClass + '">' + scoreTxt + '</span>' +
                    '</div>';
            }
            var sucursalesHtml = sucConDato.map(function(s, i) { return filaSucursal(s, posiciones[i]); }).join('') +
                sucPendientes.map(function(s) { return filaSucursal(s, null); }).join('');
            var listaTitulo = (sucConDato.length === 0 && sucPendientes.length)
                ? 'Pendientes de supervisar (' + sucPendientes.length + ')'
                : 'Sucursales del grupo' + (sucPendientes.length ? ' · ' + sucPendientes.length + ' pendiente' + (sucPendientes.length === 1 ? '' : 's') : '');

            // Tendencia por trimestre: chips que se "prenden" + flecha ↑/↓/▬
            var tendenciaHtml = '';
            if (g.tendencia && g.tendencia.length) {
                var anioTxt = g.anio || '';
                var promAnioHtml = '';
                if (g.promedio_anio !== null && g.promedio_anio !== undefined) {
                    promAnioHtml = '<span class="trend-anio ' + (g.color_anio || 'gray') + '">' +
                        'Año ' + anioTxt + ': <strong>' + fmt1(g.promedio_anio) + '</strong>' +
                        '<button type="button" class="info-i" onclick="showAcumuladoInfo(\'grupo\', ' + (anioTxt || 0) + ')" aria-label="Cómo se calcula el acumulado">i</button></span>';
                }
                tendenciaHtml = '<div class="trend-head">' +
                    '<h4 class="modal-section-title">Tendencia por trimestre</h4>' +
                    promAnioHtml +
                    '</div>' +
                    '<div class="trend-chips">' + renderTrendChips(g.tendencia) + '</div>';
            }

            var sinDatosGrupo = (g.promedio === null || g.promedio === undefined);
            var periodoLbl = periodoLabelTxt();
            var evaluadas = (g.sucursales_evaluadas !== undefined) ? g.sucursales_evaluadas : null;
            var activas = g.total_sucursales || 0;
            var parcial = !sinDatosGrupo && evaluadas !== null && evaluadas < activas;
            var evalTxt = (evaluadas !== null) ? coberturaTxt(evaluadas, activas) : '';
            body.innerHTML = '<div class="modal-kpi">' +
                '<span class="modal-kpi-value ' + (sinDatosGrupo ? 'gray' : colorClass) + (parcial ? ' partial' : '') + '" aria-label="' + escAttr(sinDatosGrupo ? 'Sin supervisión' : fmt1(g.promedio) + ', ' + nivelTxt(colorClass)) + '">' + (sinDatosGrupo ? '—' : fmt1(g.promedio)) + '</span>' +
                '<span class="modal-kpi-label">' + (sinDatosGrupo
                    ? 'Sin supervisión · ' + periodoLbl
                    : 'Calificación ' + tipoLabelTxt() + ' · ' + periodoLbl) + '</span>' +
                (evalTxt ? '<span class="modal-kpi-date">' + evalTxt + '</span>' : '') +
                '</div>' +
                '<div class="modal-stats">' +
                '<div class="modal-stat"><span class="stat-value">' + (g.total_supervisiones || 0) + '</span><span class="stat-label">' + ((g.total_supervisiones || 0) === 1 ? 'Supervisión' : 'Supervisiones') + ' · ' + periodoLbl + '</span></div>' +
                '<div class="modal-stat"><span class="stat-value">' + activas + '</span><span class="stat-label">' + (activas === 1 ? 'Sucursal' : 'Sucursales') + '</span></div>' +
                '</div>' +
                tendenciaHtml +
                '<h4 class="modal-section-title">' + listaTitulo + '</h4>' +
                '<div class="modal-list">' + sucursalesHtml + '</div>';

            // Resetear scroll DESPUÉS de cargar contenido
            setTimeout(function() {
                body.scrollTop = 0;
                if (body.scrollTo) body.scrollTo(0, 0);
            }, 50);
        })
        .catch(function(e) {
            console.error('Error loading grupo:', e);
            renderError(body, function() { openGrupoModal(grupoId); });
        });

    // Close handlers (cierran vía historial cuando el estado actual es el del modal)
    var closeBtn = document.getElementById('modalClose');
    if (closeBtn) closeBtn.onclick = function() { closeTopModal(); };
    overlay.onclick = function(e) {
        if (e.target === overlay) closeTopModal();
    };
}

function openSucursalModal(sucursalId) {
    var overlay = document.getElementById('sucursalModalOverlay');
    var body = document.getElementById('sucursalModalBody');
    var title = document.getElementById('sucursalModalTitle');
    var container = overlay ? overlay.querySelector('.modal-container') : null;

    if (!overlay || !body) return;

    var yaAbierto = overlay.classList.contains('active');
    if (!yaAbierto) {
        // iOS fix: bloquear scroll (solo incrementa contador si ya hay modal abierto)
        lockBodyScroll();
        pushModalState('sucursal', sucursalId);
    }

    // Flecha "atrás" solo tiene sentido si debajo hay un modal de grupo
    var backBtn = document.getElementById('modalBack');
    var grupoOverlay = document.getElementById('modalOverlay');
    if (backBtn) backBtn.style.visibility = (grupoOverlay && grupoOverlay.classList.contains('active')) ? '' : 'hidden';

    if (title) title.textContent = 'Sucursal';
    body.innerHTML = loadingHtml();
    body.scrollTop = 0;
    overlay.classList.add('active');

    // Forzar repaint para iOS - CRÍTICO
    forceRepaint(container);
    setTimeout(function() {
        forceRepaint(overlay);
    }, 10);
    focusModal(overlay);

    // El número/áreas reflejan el trimestre seleccionado (coincide con ranking/mapa).
    // La tendencia SÍ va sin periodo: muestra la historia trimestre a trimestre.
    var sucUrl = '/api/sucursal/' + sucursalId + '/' + currentTipo;
    if (currentPeriodoId) sucUrl += '?periodo_id=' + currentPeriodoId;

    // Cargar datos de sucursal y tendencia en paralelo (la tendencia es opcional)
    Promise.all([
        fetchJson(sucUrl),
        fetchJson('/api/sucursal-tendencia/' + sucursalId + '/' + currentTipo).catch(function() { return { data: [] }; })
    ]).then(function(results) {
        var s = results[0].data;
        var tendData = results[1];
        var sucInfo = s.sucursal || {};
        if (title) title.textContent = sucInfo.nombre || 'Sucursal';

        var colorClass = s.color || getColorClass(s.promedio);
        var esAnio = (currentPeriodoId === 'all');
        var periodoLbl = periodoLabelTxt();

        // Construir HTML de tendencia (últimas 4 supervisiones), fechas SIEMPRE con año (A8)
        var tendenciaHtml = '';
        var hayBarras = !!(tendData.data && tendData.data.length > 0);
        var ultimaBarra = hayBarras ? tendData.data[tendData.data.length - 1] : null;
        if (hayBarras) {
            var maxVal = 100;
            var barsHtml = tendData.data.map(function(t, index) {
                var height = Math.max((t.calificacion / maxVal) * 100, 5);
                var tColor = t.color || getColorClass(t.calificacion);
                var isLast = index === tendData.data.length - 1;
                var fechaIso = t.fecha_completa || '';
                var aria = (fmtFecha(fechaIso) || t.fecha) + ': ' + fmt1(t.calificacion) + ', ' + nivelTxt(tColor);
                return '<div class="trend-bar ' + (isLast ? 'selected' : '') + '" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" data-sup-id="' + t.id + '" data-fecha="' + escAttr(fechaIso) + '" onclick="loadSupervisionAreas(' + t.id + ', this)" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();loadSupervisionAreas(' + t.id + ', this)}">' +
                    '<div class="trend-fill ' + tColor + '" style="height: ' + height + '%">' +
                    '<span class="trend-value">' + fmt1(t.calificacion) + '</span>' +
                    '</div>' +
                    '<span class="trend-label">' + (fmtFechaCorta(fechaIso) || t.fecha) + '</span>' +
                    '</div>';
            }).join('');

            tendenciaHtml = '<div class="tendencia-section">' +
                '<h4 class="modal-section-title">Últimas ' + tendData.data.length + ' supervisiones</h4>' +
                '<p class="trend-hint">Toca una barra para ver sus áreas</p>' +
                '<div class="trend-chart">' + barsHtml + '</div>' +
                '</div>';
        }

        // Tendencia por trimestre (chips que se prenden + flecha), igual que el grupo
        var trendQHtml = '';
        if (s.tendencia && s.tendencia.length) {
            var sPromAnioHtml = '';
            if (s.promedio_anio !== null && s.promedio_anio !== undefined) {
                sPromAnioHtml = '<span class="trend-anio ' + (s.color_anio || 'gray') + '">' +
                    'Año ' + (s.anio || '') + ': <strong>' + fmt1(s.promedio_anio) + '</strong>' +
                    '<button type="button" class="info-i" onclick="showAcumuladoInfo(\'sucursal\', ' + (s.anio || 0) + ')" aria-label="Cómo se calcula el acumulado">i</button></span>';
            }
            trendQHtml = '<div class="trend-head">' +
                '<h4 class="modal-section-title">Tendencia por trimestre</h4>' + sPromAnioHtml +
                '</div><div class="trend-chips">' + renderTrendChips(s.tendencia) + '</div>';
        }

        // Construir HTML de áreas/KPIs (en contenedor actualizable)
        var areasHtml = '';
        var areasTypeLabel = currentTipo === 'operativas' ? 'Áreas evaluadas' : 'KPIs de seguridad';
        var areasCount = s.areas ? s.areas.length : 0;
        var infoBtn = '<button type="button" class="info-i" onclick="showAreasInfo()" aria-label="Cómo se relacionan las áreas con la calificación general">i</button>';
        var tieneAreas = !!(s.areas && s.areas.length > 0);
        if (tieneAreas) {
            areasHtml = '<div id="areasContainer" data-tipo="' + currentTipo + '">' +
                '<h4 class="modal-section-title areas-title"><span id="areasTitle">' + areasTypeLabel + ' (' + areasCount + ') · última supervisión</span>' + infoBtn + '</h4>' +
                '<div class="areas-grid" id="areasGrid">' + renderAreasCards(s.areas) + '</div></div>';
        } else if (hayBarras) {
            // A7: sin supervisión en el periodo → se cargan las áreas de la última disponible
            areasHtml = '<div id="areasContainer" data-tipo="' + currentTipo + '">' +
                '<h4 class="modal-section-title areas-title"><span id="areasTitle">' + areasTypeLabel + '</span>' + infoBtn + '</h4>' +
                '<p class="areas-note">Sin supervisión en ' + periodoLbl + ' · Última supervisión disponible: ' +
                    (fmtFecha(ultimaBarra.fecha_completa) || ultimaBarra.fecha) + '</p>' +
                '<div class="areas-grid" id="areasGrid">' + loadingHtml() + '</div></div>';
        } else {
            areasHtml = '<div id="areasContainer"><div class="empty-state">Sin supervisiones registradas para esta sucursal</div></div>';
        }

        // Info adicional
        var infoHtml = '';
        if (sucInfo.ciudad || sucInfo.estado) {
            infoHtml = '<div class="sucursal-location">' +
                '<span class="location-icon" aria-hidden="true">📍</span>' +
                '<span>' + (sucInfo.ciudad || '') + (sucInfo.ciudad && sucInfo.estado ? ', ' : '') + (sucInfo.estado || '') + '</span>' +
                '</div>';
        }

        // Número principal = MISMA definición que ranking/mapa (M1 trimestre o M3 año).
        // Si NO hubo revisión en el alcance, no mostrar "0" (rojo).
        var sinRevision = (s.promedio === null || s.promedio === undefined) || !s.fecha_supervision;
        var fechaTxt = s.fecha_supervision ? fmtFecha(String(s.fecha_supervision).split(' ')[0]) : '';
        var ultimaTxt = fechaTxt ? ('Última supervisión: ' + fechaTxt + (s.supervisor ? ' · ' + s.supervisor : '')) : '';
        var ultimaDifiere = (s.calificacion_ultima !== null && s.calificacion_ultima !== undefined &&
            s.promedio !== null && s.promedio !== undefined && fmt1(s.calificacion_ultima) !== fmt1(s.promedio));
        var kpiHtml = sinRevision
            ? '<div class="modal-kpi"><span class="modal-kpi-value gray">—</span>' +
              '<span class="modal-kpi-label">Sin supervisión · ' + periodoLbl + '</span></div>'
            : '<div class="modal-kpi">' +
              '<span class="modal-kpi-value ' + colorClass + '" aria-label="' + escAttr(fmt1(s.promedio) + ', ' + nivelTxt(colorClass)) + '">' + fmt1(s.promedio) + '</span>' +
              '<span class="modal-kpi-label">Calificación ' + tipoLabelTxt() + ' · ' + periodoLbl + '</span>' +
              (ultimaTxt ? '<span class="modal-kpi-date">' + ultimaTxt + '</span>' : '') +
              (ultimaDifiere ? '<span class="modal-kpi-date">Calificación de la última supervisión: <strong class="' + getColorClass(s.calificacion_ultima) + '">' + fmt1(s.calificacion_ultima) + '</strong>' +
                  (esAnio ? ' · el número principal promedia los trimestres del año' : ' · el número principal promedia las supervisiones del trimestre') + '</span>' : '') +
              '</div>';

        body.innerHTML = kpiHtml +
            infoHtml +
            '<div class="modal-stats">' +
            '<div class="modal-stat"><span class="stat-value">' + (s.supervisor || 'Sin asignar') + '</span><span class="stat-label">Supervisor</span></div>' +
            '<div class="modal-stat"><span class="stat-value">' + (sucInfo.grupo_nombre || '—') + '</span><span class="stat-label">Grupo</span></div>' +
            '</div>' +
            trendQHtml +
            tendenciaHtml +
            areasHtml;

        // A7: autocargar las áreas de la última supervisión disponible
        if (!tieneAreas && hayBarras) {
            var ultimaEl = body.querySelector('.trend-bar[data-sup-id="' + ultimaBarra.id + '"]');
            loadSupervisionAreas(ultimaBarra.id, ultimaEl);
        }

        // IMPORTANTE: Resetear scroll DESPUÉS de cargar contenido
        setTimeout(function() {
            body.scrollTop = 0;
            body.scrollTo && body.scrollTo(0, 0);
        }, 50);
    }).catch(function(e) {
        console.error('Error loading sucursal:', e);
        renderError(body, function() { openSucursalModal(sucursalId); });
    });

    // Close handlers: X, flecha atrás y tocar fuera cierran SOLO este modal (el de grupo sigue)
    var closeBtn = document.getElementById('sucursalModalClose');
    if (closeBtn) closeBtn.onclick = function() { closeTopModal(); };
    if (backBtn) backBtn.onclick = function() { closeTopModal(); };
    overlay.onclick = function(e) {
        if (e.target === overlay) closeTopModal();
    };
}

function renderAreasCards(areas) {
    return areas.map(function(a) {
        var aColorClass = a.color || getColorClass(a.porcentaje);
        return '<div class="area-card ' + aColorClass + '" aria-label="' + escAttr(a.nombre + ': ' + fmt1(a.porcentaje) + '%, ' + nivelTxt(aColorClass)) + '">' +
            '<span class="area-name">' + a.nombre + '</span>' +
            '<span class="area-score">' + fmt1(a.porcentaje) + '%</span>' +
            '</div>';
    }).join('');
}

function showAreasInfo() {
    var what = currentTipo === 'operativas' ? 'las áreas' : 'los KPIs';
    var calif = 'Calificación ' + tipoLabelTxt();
    showInfoPopup('¿Por qué ' + what + ' no promedian a la calificación?',
        'La <strong>' + calif + '</strong> pondera cada ' + (currentTipo === 'operativas' ? 'área' : 'KPI') + ' según su peso en la supervisión, ' +
        'por eso el promedio simple de ' + what + ' no coincide con ella. ' +
        (currentTipo === 'operativas' ? 'Las áreas sirven' : 'Los KPIs sirven') + ' para ver <strong>dónde</strong> está la oportunidad, no para recalcular el total.');
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
        areasGrid.innerHTML = '<div class="loading-inline" role="status">Cargando…</div>';
    }

    // Llamar al API
    fetchJson('/api/supervision/' + supervisionId + '/areas/' + tipo)
        .then(function(data) {
            var d = data.data;
            var areasTypeLabel = tipo === 'operativas' ? 'Áreas evaluadas' : 'KPIs de seguridad';
            var areas = d.areas || [];

            // Actualizar título
            if (areasTitle) {
                areasTitle.textContent = areasTypeLabel + ' (' + areas.length + ') · ' + (d.fecha ? fmtFecha(String(d.fecha).split(' ')[0]) : 'supervisión');
            }

            // Actualizar grid de áreas
            if (areasGrid && areas.length > 0) {
                areasGrid.innerHTML = renderAreasCards(areas);
            } else if (areasGrid) {
                areasGrid.innerHTML = '<div class="empty-state">Sin datos de áreas para esta supervisión</div>';
            }
        })
        .catch(function(e) {
            console.error('Error loading supervision areas:', e);
            if (areasGrid) {
                renderError(areasGrid, function() { loadSupervisionAreas(supervisionId, barElement); });
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

function setMapStatus(html, isError, retryFn) {
    var st = document.getElementById('mapStatus');
    if (!st) return;
    if (!html) {
        st.innerHTML = '';
        st.hidden = true;
        return;
    }
    st.hidden = false;
    st.className = 'map-status' + (isError ? ' error' : '');
    st.innerHTML = html;
    var btn = st.querySelector('.retry-btn');
    if (btn && retryFn) btn.addEventListener('click', retryFn);
}

function loadMapData() {
    if (!map) return;

    markers.forEach(function(m) { map.removeLayer(m); });
    markers = [];
    setMapStatus('<span role="status">Cargando…</span>', false);

    var url = '/api/mapa/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }

    fetchJson(url)
        .then(function(data) {
            var items = data.data || [];
            if (items.length === 0) {
                setMapStatus('Sin sucursales para mostrar', false);
                return;
            }
            var bounds = [];
            var conDato = 0;

            items.forEach(function(item) {
                if (!item.lat || !item.lng) return;

                var colorClass = item.color || 'gray';
                var color = getMarkerColor(colorClass);
                var isPendiente = item.promedio === null || item.promedio === undefined;
                if (!isPendiente) conDato++;

                var marker = L.circleMarker([item.lat, item.lng], {
                    radius: isPendiente ? 8 : 10,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: isPendiente ? 0.6 : 1,
                    fillOpacity: isPendiente ? 0.5 : 0.9
                }).addTo(map);

                // Popup con botón para ver detalle
                var scoreText = isPendiente ? 'Sin supervisión en ' + periodoLabelTxt() : fmt1(item.promedio) + ' · ' + nivelTxt(colorClass);
                var popupContent = '<div class="map-popup">' +
                    '<strong>' + item.nombre + '</strong><br>' +
                    '<span class="popup-grupo">' + (item.grupo || '—') + '</span><br>' +
                    '<span class="popup-score ' + colorClass + '">' + scoreText + '</span><br>' +
                    '<button type="button" class="popup-btn" onclick="openSucursalModal(' + item.id + ')">Ver sucursal</button>' +
                    '</div>';

                marker.bindPopup(popupContent);

                // También abrir modal al hacer doble click directamente en el marker
                marker.on('dblclick', function() {
                    openSucursalModal(item.id);
                });

                markers.push(marker);
                bounds.push([item.lat, item.lng]);
            });

            if (bounds.length > 0) {
                map.fitBounds(bounds, { padding: [20, 20] });
            }
            setMapStatus('Calificación ' + tipoLabelTxt() + ' · ' + periodoLabelTxt() + ' · ' + conDato + ' de ' + items.length + ' supervisadas', false);
        })
        .catch(function(e) {
            console.error('Error loading map:', e);
            setMapStatus(ERROR_MSG + ' <button type="button" class="retry-btn">Reintentar</button>', true, loadMapData);
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
function initHistoricoControls() {
    var seg = document.getElementById('histYearSeg');
    if (!seg) return;
    seg.addEventListener('click', function(e) {
        var btn = e.target.closest('[data-anio]');
        if (!btn || btn.disabled) return;
        var y = parseInt(btn.dataset.anio, 10);
        if (!y || y === histAnio) return;
        histAnio = y;
        loadHistorico();
    });
}

// Pinta el control segmentado "2026 | 2025" y el título "Año 2026"
function renderHistoricoHeader() {
    var seg = document.getElementById('histYearSeg');
    var title = document.getElementById('histTitle');
    var anio = anioActual || histAnio;
    if (!histAnio) histAnio = anio;
    if (title) title.textContent = 'Año ' + histAnio;
    if (seg && anio) {
        var years = [anio, anio - 1];
        seg.innerHTML = years.map(function(y) {
            return '<button type="button" class="seg-btn' + (y === histAnio ? ' active' : '') + '" data-anio="' + y + '" aria-pressed="' + (y === histAnio ? 'true' : 'false') + '">' + y + '</button>';
        }).join('');
    }
}

// Heatmap genérico: periodos = [{nombre}], grupos = [{nombre, periodos:{nombre:{promedio,color}}}], eplCas = {periodos:{...}}
function renderHeatmap(periodos, grupos, eplCas, corner) {
    var headerHtml = periodos.map(function(p) {
        return '<div class="heatmap-period" role="columnheader">' + ((p.label || p.nombre || '').substring(0, 12)) + '</div>';
    }).join('');

    function rowCells(periodosData) {
        return periodos.map(function(p) {
            var pd = (periodosData && periodosData[p.nombre]) || {};
            var val = pd.promedio;
            var tiene = (val !== null && val !== undefined);
            var colorClass = tiene ? (pd.color || getColorClass(val)) : 'gray';
            var display = tiene ? fmt1(val) : '—';
            return '<div class="heatmap-cell ' + colorClass + '" role="cell" aria-label="' + escAttr(p.nombre + ': ' + (tiene ? fmt1(val) + ', ' + nivelTxt(colorClass) : 'sin datos')) + '">' + display + '</div>';
        }).join('');
    }

    // 1) Fila "PROMEDIO" SIEMPRE primero, resaltada
    var eplHtml = '';
    if (eplCas) {
        eplHtml = '<div class="heatmap-row heatmap-total" role="row">' +
            '<div class="heatmap-entity" role="rowheader" title="Promedio EPL CAS">Promedio</div>' +
            rowCells(eplCas.periodos) +
            '</div>';
    }

    // 2) TODOS los grupos (sin límite), ya vienen ordenados mayor→menor
    var bodyHtml = grupos.map(function(g) {
        return '<div class="heatmap-row" role="row">' +
            '<div class="heatmap-entity" role="rowheader" title="' + escAttr(g.nombre) + '">' + g.nombre + '</div>' +
            rowCells(g.periodos) +
            '</div>';
    }).join('');

    return '<div class="heatmap-table" role="table">' +
        '<div class="heatmap-header" role="row">' +
        '<div class="heatmap-corner" role="columnheader">' + (corner || 'Grupo') + '</div>' +
        headerHtml +
        '</div>' +
        '<div class="heatmap-body">' + eplHtml + bodyHtml + '</div>' +
        '</div>';
}

// Oculta columnas de trimestres FUTUROS sin ningún dato (Q4 hoy)
function periodosConDato(periodos, grupos, eplCas) {
    return periodos.filter(function(p) {
        var hay = !!(eplCas && eplCas.periodos && eplCas.periodos[p.nombre] && eplCas.periodos[p.nombre].promedio !== null && eplCas.periodos[p.nombre].promedio !== undefined);
        if (!hay) {
            hay = grupos.some(function(g) {
                var pd = g.periodos && g.periodos[p.nombre];
                return pd && pd.promedio !== null && pd.promedio !== undefined;
            });
        }
        if (hay) return true;
        // Sin datos: se muestra solo si es un periodo ya iniciado y no futuro (p. ej. trimestre en curso recién abierto)
        var pd = periodosDisponibles.find(function(x) { return x.nombre === p.nombre || x.codigo === p.nombre; });
        return !!(pd && !pd.futuro);
    });
}

function loadHistorico() {
    var container = document.getElementById('heatmapContainer');
    if (!container) return;
    renderHistoricoHeader();
    container.innerHTML = loadingHtml();

    var esAnioActual = !anioActual || !histAnio || histAnio === anioActual;
    var url = '/api/historico/' + currentTipo + (esAnioActual ? '' : '?anio=' + histAnio);
    var tipoTxt = tipoLabelTxt();

    fetchJson(url)
        .then(function(data) {
            var d = data.data || {};

            if (!esAnioActual && (d.locales || d.foraneas)) {
                // Año con DOS calendarios (2025): dos heatmaps apilados, nunca mezclados con el año en curso
                var loc = d.locales || { periodos: [], grupos: [], epl_cas: null };
                var forr = d.foraneas || { periodos: [], grupos: [], epl_cas: null };
                // Columnas con el código del calendario (T1 2025 / S1 2025), no "Q1 2025"
                [loc, forr].forEach(function(cal) {
                    (cal.periodos || []).forEach(function(p) {
                        var pref = (p.codigo || '').split('-')[0];
                        p.label = pref ? (pref + ' ' + histAnio) : p.nombre;
                    });
                });
                var html = '<p class="hist-note">En ' + histAnio + ' se auditó con dos calendarios; no es comparable trimestre a trimestre con ' + (anioActual || '') + '.</p>';
                html += '<h4 class="hist-subtitle">Locales · trimestres ' + rangoPeriodos(loc.periodos, 'T1–T4') + '</h4>';
                html += (loc.grupos && loc.grupos.length)
                    ? renderHeatmap(loc.periodos || [], loc.grupos, loc.epl_cas, 'Grupo')
                    : '<div class="empty-state">Sin datos de locales en ' + histAnio + '</div>';
                html += '<h4 class="hist-subtitle">Foráneas · semestres ' + rangoPeriodos(forr.periodos, 'S1–S2') + '</h4>';
                html += (forr.grupos && forr.grupos.length)
                    ? renderHeatmap(forr.periodos || [], forr.grupos, forr.epl_cas, 'Grupo')
                    : '<div class="empty-state">Sin datos de foráneas en ' + histAnio + '</div>';
                html += '<div class="dist-legend">Calificación ' + tipoTxt + ' · Excelente ≥90 · Bueno 80–89 · Regular 70–79 · Crítico &lt;70</div>';
                container.innerHTML = html;
                return;
            }

            var grupos = d.grupos || [];
            var eplCas = d.epl_cas || null;
            if (grupos.length === 0) {
                container.innerHTML = '<div class="empty-state">No hay datos históricos para ' + histAnio + '</div>';
                return;
            }
            var periodos = periodosConDato(d.periodos || [], grupos, eplCas);
            container.innerHTML = renderHeatmap(periodos, grupos, eplCas, 'Grupo') +
                '<div class="dist-legend">Calificación ' + tipoTxt + ' · ' + grupos.length + ' grupos · Excelente ≥90 · Bueno 80–89 · Regular 70–79 · Crítico &lt;70</div>';
        })
        .catch(function(e) {
            console.error('Error loading historico:', e);
            renderError(container, loadHistorico);
        });
}

// "T1–T4" a partir de los códigos de periodo (T1-2025 → T1)
function rangoPeriodos(periodos, fallback) {
    if (!periodos || !periodos.length) return fallback;
    var cods = periodos.map(function(p) { return (p.codigo || p.nombre || '').split(/[- ]/)[0]; }).filter(Boolean);
    if (!cods.length) return fallback;
    return cods.length === 1 ? cods[0] : cods[0] + '–' + cods[cods.length - 1];
}

// ========== ALERTAS ==========
function loadAlertas() {
    var critContainer = document.getElementById('alertasCriticos');
    var warnContainer = document.getElementById('alertasWarning');
    var gruposContainer = document.getElementById('alertasGrupos');
    var pendContainer = document.getElementById('alertasPendientes');
    var summaryContainer = document.getElementById('alertasSummary');
    var scopeEl = document.getElementById('alertasScope');

    if (critContainer) critContainer.innerHTML = loadingHtml();
    if (warnContainer) warnContainer.innerHTML = loadingHtml();
    if (gruposContainer) gruposContainer.innerHTML = loadingHtml();
    if (pendContainer) pendContainer.innerHTML = loadingHtml();
    if (scopeEl) scopeEl.textContent = 'Calificación ' + tipoLabelTxt() + ' · ' + periodoLabelTxt();

    var url = '/api/alertas/' + currentTipo;
    if (currentPeriodoId) {
        url += '?periodo_id=' + currentPeriodoId;
    }

    fetchJson(url)
        .then(function(data) {
            var d = data.data || {};
            var alertas = d.alertas || [];
            var periodoLbl = periodoLabelTxt();
            // Sucursales por nivel (misma regla que la Distribución del header)
            var criticos = alertas.filter(function(a) { return a.tipo === 'critical'; });
            var regulares = d.sucursales_regulares || [];
            var pendientes = d.pendientes || [];
            // Grupos por nivel (promedio del grupo): sección propia, NO se suman a las tarjetas
            var gruposCriticos = d.grupos_criticos || [];
            var gruposRiesgo = d.grupos_riesgo || alertas.filter(function(a) { return a.tipo === 'warning'; });
            var totalCriticos = (d.total_criticos !== undefined) ? d.total_criticos : criticos.length;
            var totalRegulares = (d.total_regulares !== undefined) ? d.total_regulares : regulares.length;
            var totalPend = (d.total_pendientes !== undefined) ? d.total_pendientes : pendientes.length;

            function tarjeta(cls, n, label, sub) {
                return '<div class="alert-summary-card ' + cls + '" aria-label="' + n + ' sucursales ' + label.toLowerCase() + '">' +
                    '<span class="alert-count' + (n === 0 ? ' zero' : '') + '">' + n + '</span>' +
                    '<span class="alert-label">' + label + '</span>' +
                    '<span class="alert-sub">' + sub + '</span>' +
                    '</div>';
            }
            if (summaryContainer) {
                summaryContainer.innerHTML =
                    tarjeta('critical', totalCriticos, 'Críticas', 'sucursales &lt;70') +
                    tarjeta('regular', totalRegulares, 'Regulares', 'sucursales 70–79') +
                    tarjeta('pending', totalPend, 'Pendientes', 'sin supervisión');
            }

            // Fila de grupo: nombre + pill de nivel + cobertura; la cifra en color una sola vez
            function grupoAlerta(g, cls) {
                var prom = g.promedio;
                var nombre = g.grupo_nombre || g.nombre || '';
                var nivel = nivelTxt(getColorClass(prom));
                var aria = 'Grupo ' + nombre + ', ' + fmt1(prom) + ', ' + nivel + ', ' + coberturaTxt(g.evaluadas, g.activas);
                return '<div class="alerta-item ' + cls + ' grupo" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" onclick="openGrupoModal(' + g.grupo_id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openGrupoModal(' + g.grupo_id + ')}">' +
                    '<div class="alerta-info">' +
                    '<span class="alerta-name" title="' + escAttr(nombre) + '"><span class="alerta-pill ' + cls + '">' + nivel + '</span>' + nombre + '</span>' +
                    '<span class="alerta-meta">Promedio del grupo · ' + coberturaTxt(g.evaluadas, g.activas) + '</span>' +
                    '</div>' +
                    '<span class="alerta-score">' + fmt1(prom) + '</span>' +
                    '</div>';
            }

            // Fila de sucursal: nombre (sin prefijo; el encabezado ya dice el nivel), grupo, cifra una vez
            function sucursalAlerta(item, cls) {
                var nombre = item.sucursal_nombre || item.nombre || (item.titulo || '').replace(/^.*?:\s*/, '');
                var grupo = item.grupo_nombre || item.grupo || '';
                var aria = nombre + ', ' + fmt1(item.promedio) + ', ' + nivelTxt(cls) + (grupo ? ', ' + grupo : '');
                return '<div class="alerta-item ' + cls + '" role="button" tabindex="0" aria-label="' + escAttr(aria) + '" onclick="openSucursalModal(' + item.sucursal_id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSucursalModal(' + item.sucursal_id + ')}">' +
                    '<div class="alerta-info">' +
                    '<span class="alerta-name" title="' + escAttr(nombre) + '">' + nombre + '</span>' +
                    '<span class="alerta-meta">' + (grupo || '—') + '</span>' +
                    '</div>' +
                    '<span class="alerta-score">' + fmt1(item.promedio) + '</span>' +
                    '</div>';
            }

            if (critContainer) {
                critContainer.innerHTML = criticos.length
                    ? criticos.map(function(a) { return sucursalAlerta(a, 'critical'); }).join('')
                    : '<div class="empty-state success-msg">✓ Ninguna sucursal por debajo de 70 en ' + periodoLbl + '</div>';
            }

            if (warnContainer) {
                warnContainer.innerHTML = regulares.length
                    ? regulares.map(function(a) { return sucursalAlerta(a, 'regular'); }).join('')
                    : '<div class="empty-state success-msg">✓ Ninguna sucursal en 70–79 en ' + periodoLbl + '</div>';
            }

            if (gruposContainer) {
                var gruposTitle = document.getElementById('gruposTitle');
                var nGrupos = gruposCriticos.length + gruposRiesgo.length;
                if (gruposTitle) gruposTitle.textContent = 'Grupos que requieren atención' + (nGrupos ? ' (' + nGrupos + ')' : '');
                gruposContainer.innerHTML = nGrupos
                    ? gruposCriticos.map(function(g) { return grupoAlerta(g, 'critical'); }).join('') +
                      gruposRiesgo.map(function(g) { return grupoAlerta(g, 'regular'); }).join('')
                    : '<div class="empty-state success-msg">✓ Ningún grupo con promedio menor a 80 en ' + periodoLbl + '</div>';
            }

            if (pendContainer) {
                var pendTitle = document.getElementById('pendientesTitle');
                if (pendTitle) pendTitle.textContent = 'Pendientes de supervisar (' + totalPend + ')';
                if (pendientes.length === 0) {
                    pendContainer.innerHTML = '<div class="empty-state success-msg">' +
                        '✓ Todas las sucursales activas ya fueron supervisadas en ' + periodoLabelTxt() + '</div>';
                } else {
                    // Agrupadas por grupo operativo
                    var porGrupo = {};
                    var orden = [];
                    pendientes.forEach(function(p) {
                        var k = p.grupo || '—';
                        if (!porGrupo[k]) { porGrupo[k] = []; orden.push(k); }
                        porGrupo[k].push(p);
                    });
                    pendContainer.innerHTML = orden.map(function(k) {
                        var items = porGrupo[k].map(function(p) {
                            return '<div class="alerta-item pending" role="button" tabindex="0" aria-label="' + escAttr(p.nombre + ', pendiente de supervisar, ' + k) + '" onclick="openSucursalModal(' + p.sucursal_id + ')" onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSucursalModal(' + p.sucursal_id + ')}">' +
                                '<div class="alerta-info">' +
                                '<span class="alerta-name" title="' + escAttr(p.nombre) + '">' + p.nombre + '</span>' +
                                '<span class="alerta-meta">Sin supervisión en ' + periodoLabelTxt() + '</span>' +
                                '</div>' +
                                '<span class="alerta-score gray">—</span>' +
                                '</div>';
                        }).join('');
                        return '<div class="pending-group">' +
                            '<div class="pending-group-title">' + k + ' <span class="pending-count">' + porGrupo[k].length + '</span></div>' +
                            items + '</div>';
                    }).join('');
                }
            }
        })
        .catch(function(e) {
            console.error('Error loading alertas:', e);
            if (summaryContainer) summaryContainer.innerHTML = '';
            if (critContainer) renderError(critContainer, loadAlertas);
            if (warnContainer) warnContainer.innerHTML = '';
            if (gruposContainer) gruposContainer.innerHTML = '';
            if (pendContainer) pendContainer.innerHTML = '';
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
