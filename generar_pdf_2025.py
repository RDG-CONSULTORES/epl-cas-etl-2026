#!/usr/bin/env python3
"""
EPL CAS 2025 - Reporte de Premios para Convención
Genera PDF profesional con rankings de sucursales y grupos operativos
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURACIÓN
# ============================================================
DATABASE_URL = os.environ['DATABASE_URL']
OUTPUT_FILE = '/Users/robertodavila/epl-cas-etl-2026/EPL_CAS_2025_Premios_Convencion.pdf'

# Colores EPL
EPL_ROJO = colors.HexColor('#C41E3A')
EPL_ROJO_OSCURO = colors.HexColor('#8B0000')
EPL_DORADO = colors.HexColor('#D4A017')
EPL_GRIS_OSCURO = colors.HexColor('#2C2C2C')
EPL_GRIS = colors.HexColor('#4A4A4A')
EPL_GRIS_CLARO = colors.HexColor('#F5F5F5')
VERDE = colors.HexColor('#1B7A3D')
VERDE_CLARO = colors.HexColor('#E8F5E9')
AMARILLO = colors.HexColor('#F9A825')
AMARILLO_CLARO = colors.HexColor('#FFF8E1')
NARANJA = colors.HexColor('#E65100')
NARANJA_CLARO = colors.HexColor('#FFF3E0')
ROJO_CLARO = colors.HexColor('#FFEBEE')
BLANCO = colors.white
NEGRO = colors.black

def get_color_row(valor):
    """Retorna color de fondo según calificación"""
    if valor >= 90:
        return VERDE_CLARO
    elif valor >= 80:
        return AMARILLO_CLARO
    elif valor >= 70:
        return NARANJA_CLARO
    else:
        return ROJO_CLARO

def get_color_text(valor):
    """Retorna color de texto según calificación"""
    if valor >= 90:
        return VERDE
    elif valor >= 80:
        return AMARILLO
    elif valor >= 70:
        return NARANJA
    else:
        return EPL_ROJO

def get_medalla(pos):
    """Retorna emoji/texto de medalla para top 3"""
    if pos == 1:
        return "1"
    elif pos == 2:
        return "2"
    elif pos == 3:
        return "3"
    return str(pos)

# ============================================================
# CONSULTAS A BASE DE DATOS
# ============================================================
def fetch_data():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # --- Sucursales con promedios operativos y seguridad ---
    cur.execute('''
        SELECT
            s.id, s.nombre, s.numero, s.clasificacion,
            g.nombre as grupo,
            ROUND(AVG(so.calificacion_general)::numeric, 2) as prom_op,
            COUNT(so.id) as evals_op
        FROM sucursales s
        JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
        JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            AND EXTRACT(YEAR FROM so.fecha_supervision) = 2025
        WHERE s.activo = true
        GROUP BY s.id, s.nombre, s.numero, s.clasificacion, g.nombre
        HAVING COUNT(so.id) > 0
    ''')
    sucs_op = {r['id']: r for r in cur.fetchall()}

    cur.execute('''
        SELECT
            s.id,
            ROUND(AVG(ss.calificacion_general)::numeric, 2) as prom_seg,
            COUNT(ss.id) as evals_seg
        FROM sucursales s
        JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
            AND EXTRACT(YEAR FROM ss.fecha_supervision) = 2025
        WHERE s.activo = true
        GROUP BY s.id
    ''')
    seg_map = {r['id']: r for r in cur.fetchall()}

    sucursales = []
    for sid, s in sucs_op.items():
        seg = seg_map.get(sid, {})
        sucursales.append({
            'nombre': s['nombre'],
            'grupo': s['grupo'],
            'clasificacion': s['clasificacion'],
            'prom_op': float(s['prom_op']),
            'evals_op': s['evals_op'],
            'prom_seg': float(seg.get('prom_seg') or 0),
            'evals_seg': seg.get('evals_seg', 0),
        })

    # --- Grupos operativos ---
    cur.execute('''
        SELECT
            g.id, g.nombre,
            ROUND(AVG(so.calificacion_general)::numeric, 2) as prom_op,
            COUNT(so.id) as evals_op,
            COUNT(DISTINCT so.sucursal_id) as sucs_evaluadas,
            (SELECT COUNT(*) FROM sucursales ss WHERE ss.grupo_operativo_id = g.id AND ss.activo = true) as total_sucs
        FROM grupos_operativos g
        JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
        JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            AND EXTRACT(YEAR FROM so.fecha_supervision) = 2025
        WHERE g.activo = true
        GROUP BY g.id, g.nombre
    ''')
    grupos_op = {r['id']: r for r in cur.fetchall()}

    cur.execute('''
        SELECT
            g.id,
            ROUND(AVG(ss.calificacion_general)::numeric, 2) as prom_seg,
            COUNT(ss.id) as evals_seg
        FROM grupos_operativos g
        JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
        JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
            AND EXTRACT(YEAR FROM ss.fecha_supervision) = 2025
        WHERE g.activo = true
        GROUP BY g.id
    ''')
    gseg_map = {r['id']: r for r in cur.fetchall()}

    grupos = []
    for gid, g in grupos_op.items():
        seg = gseg_map.get(gid, {})
        grupos.append({
            'nombre': g['nombre'],
            'prom_op': float(g['prom_op']),
            'evals_op': g['evals_op'],
            'sucs_evaluadas': g['sucs_evaluadas'],
            'total_sucs': g['total_sucs'],
            'prom_seg': float(seg.get('prom_seg') or 0),
            'evals_seg': seg.get('evals_seg', 0),
        })

    conn.close()
    return sucursales, grupos

# ============================================================
# FUNCIONES DE RANKING
# ============================================================
def rank_list(items):
    """Ordena por prom_op DESC, desempate prom_seg DESC. Asigna posiciones con empate técnico."""
    items.sort(key=lambda x: (-x['prom_op'], -x['prom_seg']))
    pos = 1
    for i, item in enumerate(items):
        if i > 0 and item['prom_op'] == items[i-1]['prom_op'] and item['prom_seg'] == items[i-1]['prom_seg']:
            item['pos'] = items[i-1]['pos']
        else:
            item['pos'] = pos
        pos += 1
    return items

# ============================================================
# GENERACIÓN DEL PDF
# ============================================================
def build_pdf(sucursales, grupos):
    doc = SimpleDocTemplate(
        OUTPUT_FILE,
        pagesize=letter,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()

    # Estilos personalizados
    style_title = ParagraphStyle(
        'EPLTitle', parent=styles['Title'],
        fontSize=28, textColor=EPL_ROJO_OSCURO, alignment=TA_CENTER,
        spaceAfter=6, fontName='Helvetica-Bold',
    )
    style_subtitle = ParagraphStyle(
        'EPLSubtitle', parent=styles['Normal'],
        fontSize=14, textColor=EPL_GRIS, alignment=TA_CENTER,
        spaceAfter=4, fontName='Helvetica',
    )
    style_section = ParagraphStyle(
        'EPLSection', parent=styles['Heading1'],
        fontSize=16, textColor=EPL_ROJO_OSCURO, alignment=TA_LEFT,
        spaceBefore=10, spaceAfter=8, fontName='Helvetica-Bold',
        borderWidth=0, borderPadding=0,
    )
    style_obs_title = ParagraphStyle(
        'ObsTitle', parent=styles['Heading2'],
        fontSize=12, textColor=EPL_ROJO_OSCURO, alignment=TA_LEFT,
        spaceBefore=6, spaceAfter=3, fontName='Helvetica-Bold',
    )
    style_obs = ParagraphStyle(
        'Obs', parent=styles['Normal'],
        fontSize=9.5, textColor=EPL_GRIS_OSCURO, alignment=TA_JUSTIFY,
        spaceBefore=2, spaceAfter=4, fontName='Helvetica',
        leading=13,
    )
    style_footer = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#999999'), alignment=TA_CENTER,
    )
    style_cell = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=8, textColor=NEGRO, fontName='Helvetica', leading=10,
    )
    style_cell_bold = ParagraphStyle(
        'CellBold', parent=styles['Normal'],
        fontSize=8, textColor=NEGRO, fontName='Helvetica-Bold', leading=10,
    )
    style_cell_center = ParagraphStyle(
        'CellCenter', parent=style_cell, alignment=TA_CENTER,
    )
    style_cell_right = ParagraphStyle(
        'CellRight', parent=style_cell, alignment=TA_RIGHT,
    )

    elements = []

    # ============================================================
    # PORTADA
    # ============================================================
    elements.append(Spacer(1, 1.8*inch))

    # Línea decorativa superior
    d = Drawing(500, 4)
    d.add(Rect(0, 0, 500, 4, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("EL POLLO LOCO MÉXICO", style_title))
    elements.append(Spacer(1, 6))

    style_cover_sub = ParagraphStyle(
        'CoverSub', parent=style_subtitle,
        fontSize=18, textColor=EPL_DORADO, fontName='Helvetica-Bold',
    )
    elements.append(Paragraph("PREMIOS EPL CAS 2025", style_cover_sub))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Calificación, Auditoría y Seguimiento", style_subtitle))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Resultados Anuales — Convención de la Marca", style_subtitle))

    elements.append(Spacer(1, 30))

    # Línea decorativa inferior
    d2 = Drawing(500, 4)
    d2.add(Rect(0, 0, 500, 4, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d2)

    elements.append(Spacer(1, 40))

    # Datos de portada
    style_dato = ParagraphStyle(
        'Dato', parent=styles['Normal'],
        fontSize=12, textColor=EPL_GRIS, alignment=TA_CENTER,
        fontName='Helvetica', spaceAfter=6,
    )
    n_locales = len([s for s in sucursales if s['clasificacion'] == 'local'])
    n_foraneas = len([s for s in sucursales if s['clasificacion'] == 'foraneo'])
    n_total = n_locales + n_foraneas
    n_evals = sum(s['evals_op'] for s in sucursales)
    elements.append(Paragraph(f"{n_total} Sucursales Evaluadas  |  {len(grupos)} Grupos Operativos  |  {n_evals} Supervisiones", style_dato))
    elements.append(Paragraph(f"{n_locales} Locales  |  {n_foraneas} Foráneas", style_dato))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Período: Enero – Diciembre 2025", style_dato))

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d de %B de %Y').replace('February', 'Febrero')}",
        style_footer
    ))
    elements.append(Paragraph("RDG Consultores — Confidencial", style_footer))

    elements.append(PageBreak())

    # ============================================================
    # FUNCIÓN HELPER: Crear tabla de ranking
    # ============================================================
    def make_ranking_table(items, show_grupo=True):
        if show_grupo:
            header = ['Pos', 'Sucursal', 'Grupo Operativo', 'Prom.\nOperativo', 'Prom.\nSeguridad']
            col_widths = [0.45*inch, 2.1*inch, 2.1*inch, 1.0*inch, 1.0*inch]
        else:
            header = ['Pos', 'Grupo Operativo', 'Prom.\nOperativo', 'Prom.\nSeguridad', 'Sucursales\nEvaluadas']
            col_widths = [0.45*inch, 2.8*inch, 1.0*inch, 1.0*inch, 1.1*inch]

        data = [header]

        for item in items:
            pos_str = str(item['pos'])
            prom_op = f"{item['prom_op']:.2f}%"
            prom_seg = f"{item['prom_seg']:.2f}%"

            if show_grupo:
                row = [
                    pos_str,
                    item['nombre'],
                    item['grupo'],
                    prom_op,
                    prom_seg,
                ]
            else:
                sucs = f"{item['sucs_evaluadas']}/{item['total_sucs']}"
                row = [
                    pos_str,
                    item['nombre'],
                    prom_op,
                    prom_seg,
                    sucs,
                ]
            data.append(row)

        table = Table(data, colWidths=col_widths, repeatRows=1)

        # Estilos de tabla
        style_cmds = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), BLANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),

            # Cuerpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),

            # Alineaciones
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),   # Pos
            ('ALIGN', (3, 1), (-1, -1), 'CENTER'),   # Números

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ]

        # Colores de fila por calificación + resaltar top 3
        for i, item in enumerate(items):
            row_idx = i + 1
            bg = get_color_row(item['prom_op'])

            # Fondo según calificación
            style_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

            # Top 3: borde dorado y negrita
            if item['pos'] <= 3:
                style_cmds.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
                style_cmds.append(('FONTSIZE', (0, row_idx), (-1, row_idx), 8))
                if item['pos'] == 1:
                    style_cmds.append(('TEXTCOLOR', (0, row_idx), (0, row_idx), EPL_DORADO))
                    style_cmds.append(('FONTNAME', (0, row_idx), (0, row_idx), 'Helvetica-Bold'))
                    style_cmds.append(('FONTSIZE', (0, row_idx), (0, row_idx), 10))

        table.setStyle(TableStyle(style_cmds))
        return table

    # ============================================================
    # PÁGINA 2: RANKING SUCURSALES LOCALES
    # ============================================================
    locales = [s for s in sucursales if s['clasificacion'] == 'local']
    locales = rank_list(locales)

    elements.append(Paragraph("RANKING DE SUCURSALES LOCALES 2025", style_section))

    # Línea roja
    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 4))

    info = ParagraphStyle('Info', parent=styles['Normal'], fontSize=9, textColor=EPL_GRIS, fontName='Helvetica')
    elements.append(Paragraph(
        f"<b>{len(locales)}</b> sucursales evaluadas  |  "
        f"Desempate: Supervisión de Seguridad",
        info
    ))
    elements.append(Spacer(1, 8))

    elements.append(make_ranking_table(locales, show_grupo=True))

    # Leyenda de colores
    elements.append(Spacer(1, 8))
    leyenda_style = ParagraphStyle('Leyenda', parent=styles['Normal'], fontSize=7, textColor=EPL_GRIS)
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> ≥90% Excelente  '
        '<font color="#F9A825">■</font> 80-89% Bueno  '
        '<font color="#E65100">■</font> 70-79% Regular  '
        '<font color="#C41E3A">■</font> &lt;70% Crítico',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 3: RANKING SUCURSALES FORÁNEAS
    # ============================================================
    foraneas = [s for s in sucursales if s['clasificacion'] == 'foraneo']
    foraneas = rank_list(foraneas)

    elements.append(Paragraph("RANKING DE SUCURSALES FORÁNEAS 2025", style_section))

    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 4))

    elements.append(Paragraph(
        f"<b>{len(foraneas)}</b> sucursales evaluadas  |  "
        f"Desempate: Supervisión de Seguridad",
        info
    ))
    elements.append(Spacer(1, 8))

    elements.append(make_ranking_table(foraneas, show_grupo=True))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> ≥90% Excelente  '
        '<font color="#F9A825">■</font> 80-89% Bueno  '
        '<font color="#E65100">■</font> 70-79% Regular  '
        '<font color="#C41E3A">■</font> &lt;70% Crítico',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 4: OBSERVACIONES
    # ============================================================
    elements.append(Paragraph("OBSERVACIONES Y NOTAS METODOLÓGICAS", style_section))

    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 10))

    # --- Observación: Cobertura ---
    elements.append(Paragraph("Cobertura de Evaluaciones", style_obs_title))
    elements.append(Paragraph(
        "Se evaluaron <b>80 de 86 sucursales activas</b> (93% de cobertura). "
        "Las 6 sucursales sin evaluación en 2025 son: "
        "<b>85 - Diego Díaz</b> (OGAS), <b>83 - Cerradas de Anáhuac</b> (Grupo CADE), "
        "<b>84 - Aeropuerto del Norte</b> (EPL SO), <b>35 - Apodaca</b> (PLOG Nuevo León), "
        "<b>86 - Miguel de la Madrid</b> (PLOG Nuevo León) y "
        "<b>82 - Aeropuerto Nuevo Laredo</b> (EXPO). "
        "Estas sucursales no participan en el ranking.",
        style_obs
    ))

    # --- Observación: Metodología ---
    elements.append(Paragraph("Metodología de Ranking", style_obs_title))
    elements.append(Paragraph(
        "El ranking se determina por el <b>promedio anual de la Supervisión Operativa</b> (calificación general). "
        "Las sucursales locales fueron evaluadas trimestralmente (Q1, Q2, Q3, Q4) y "
        "las sucursales foráneas semestralmente. "
        "El promedio final se calcula con todas las evaluaciones realizadas durante 2025.",
        style_obs
    ))

    # --- Observación: Desempate ---
    elements.append(Paragraph("Criterio de Desempate", style_obs_title))
    elements.append(Paragraph(
        "En caso de <b>empate en el promedio de Supervisión Operativa</b>, el desempate se resuelve con "
        "el promedio de <b>Supervisión de Seguridad</b> (mayor promedio gana). "
        "Si persiste el empate técnico (mismo operativo y mismo seguridad), ambas sucursales o grupos "
        "comparten la misma posición en el ranking.",
        style_obs
    ))

    # --- Observación: Empate notable ---
    elements.append(Paragraph("Empate Notable: 1er Lugar Sucursales Locales", style_obs_title))
    elements.append(Paragraph(
        "Las sucursales <b>21 - Chapultepec</b> (TEC) y <b>14 - Aztlán</b> (OGAS) lograron ambas "
        "un promedio operativo perfecto de <b>100.00%</b>. El desempate se resolvió a favor de "
        "Chapultepec con <b>99.45%</b> en seguridad vs <b>97.80%</b> de Aztlán.",
        style_obs
    ))

    # --- Observación: Grupos destacados ---
    elements.append(Paragraph("Datos Destacados por Grupo", style_obs_title))
    elements.append(Paragraph(
        "<b>Grupo CADE</b> lidera el ranking de grupos con 98.96% operativo. "
        "<b>OGAS</b> (2do lugar con 98.35%) destaca por su consistencia en todas sus sucursales evaluadas. "
        "<b>PLOG Querétaro</b> (3er lugar con 96.94%) domina el top de sucursales foráneas con sus 4 sucursales. "
        "<b>PLOG Laguna</b> (7mo lugar) se posiciona como el mejor grupo foráneo de la zona norte.",
        style_obs
    ))

    # --- Observación: Desempeño general ---
    elements.append(Paragraph("Desempeño General de la Cadena", style_obs_title))

    total_sucs = len(locales) + len(foraneas)
    excelentes = len([s for s in locales + foraneas if s['prom_op'] >= 90])
    buenos = len([s for s in locales + foraneas if 80 <= s['prom_op'] < 90])
    regulares = len([s for s in locales + foraneas if 70 <= s['prom_op'] < 80])
    criticos = len([s for s in locales + foraneas if s['prom_op'] < 70])

    prom_gral_op = sum(s['prom_op'] for s in locales + foraneas) / total_sucs
    prom_gral_seg = sum(s['prom_seg'] for s in locales + foraneas) / total_sucs

    elements.append(Paragraph(
        f"Promedio general operativo de la cadena: <b>{prom_gral_op:.2f}%</b> | "
        f"Promedio general seguridad: <b>{prom_gral_seg:.2f}%</b><br/>"
        f"Distribución: <font color='#1B7A3D'><b>{excelentes}</b> excelentes (≥90%)</font>, "
        f"<font color='#F9A825'><b>{buenos}</b> buenas (80-89%)</font>, "
        f"<font color='#E65100'><b>{regulares}</b> regulares (70-79%)</font>, "
        f"<font color='#C41E3A'><b>{criticos}</b> críticas (&lt;70%)</font>.",
        style_obs
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 5: RANKING POR GRUPOS OPERATIVOS
    # ============================================================
    grupos_ranked = rank_list(grupos)

    elements.append(Paragraph("RANKING POR GRUPOS OPERATIVOS 2025", style_section))

    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 4))

    elements.append(Paragraph(
        f"<b>{len(grupos_ranked)}</b> grupos operativos  |  "
        f"Criterio: Promedio Supervisión Operativa  |  "
        f"Desempate: Supervisión de Seguridad",
        info
    ))
    elements.append(Spacer(1, 8))

    elements.append(make_ranking_table(grupos_ranked, show_grupo=False))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> ≥90% Excelente  '
        '<font color="#F9A825">■</font> 80-89% Bueno  '
        '<font color="#E65100">■</font> 70-79% Regular  '
        '<font color="#C41E3A">■</font> &lt;70% Crítico',
        leyenda_style
    ))

    elements.append(Spacer(1, 20))

    # Nota al pie
    elements.append(Paragraph(
        "Nota: La columna 'Sucursales Evaluadas' muestra cuántas sucursales del grupo fueron evaluadas "
        "del total de sucursales activas asignadas al grupo.",
        ParagraphStyle('Nota', parent=styles['Normal'], fontSize=7.5, textColor=EPL_GRIS, fontName='Helvetica-Oblique')
    ))

    # ============================================================
    # PIE DE PÁGINA EN ÚLTIMA PÁGINA
    # ============================================================
    elements.append(Spacer(1, 0.5*inch))
    d = Drawing(500, 1)
    d.add(Rect(0, 0, 500, 1, fillColor=colors.HexColor('#CCCCCC'), strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "El Pollo Loco México — Sistema CAS (Calificación, Auditoría y Seguimiento) — "
        f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')} — RDG Consultores — Confidencial",
        style_footer
    ))

    # BUILD
    doc.build(elements)
    print(f"\nPDF generado: {OUTPUT_FILE}")

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print("Obteniendo datos de la base de datos...")
    sucursales, grupos = fetch_data()
    print(f"  Sucursales: {len(sucursales)} evaluadas")
    print(f"  Grupos: {len(grupos)}")

    print("Generando PDF...")
    build_pdf(sucursales, grupos)
    print("Listo!")
