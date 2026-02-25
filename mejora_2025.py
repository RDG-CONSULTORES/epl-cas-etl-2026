#!/usr/bin/env python3
"""
EPL CAS 2025 - Premio a la Mayor Mejora
Genera PDF con rankings de mejora por Grupo Operativo y Sucursal
Comparación: Locales T1 vs T4 | Foráneas S1 vs S2
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURACIÓN
# ============================================================
DATABASE_URL = os.environ['DATABASE_URL']
OUTPUT_FILE = '/Users/robertodavila/epl-cas-etl-2026/EPL_CAS_2025_Premio_Mejora.pdf'

# Colores EPL
EPL_ROJO = colors.HexColor('#C41E3A')
EPL_ROJO_OSCURO = colors.HexColor('#8B0000')
EPL_DORADO = colors.HexColor('#D4A017')
EPL_GRIS_OSCURO = colors.HexColor('#2C2C2C')
EPL_GRIS = colors.HexColor('#4A4A4A')
VERDE = colors.HexColor('#1B7A3D')
VERDE_CLARO = colors.HexColor('#E8F5E9')
AMARILLO = colors.HexColor('#F9A825')
AMARILLO_CLARO = colors.HexColor('#FFF8E1')
NARANJA = colors.HexColor('#E65100')
NARANJA_CLARO = colors.HexColor('#FFF3E0')
ROJO_CLARO = colors.HexColor('#FFEBEE')
BLANCO = colors.white
NEGRO = colors.black
AZUL_MEJORA = colors.HexColor('#1565C0')
AZUL_CLARO = colors.HexColor('#E3F2FD')

def get_color_mejora(mejora):
    """Color de fondo según nivel de mejora"""
    if mejora >= 10:
        return VERDE_CLARO
    elif mejora >= 5:
        return AZUL_CLARO
    elif mejora >= 0:
        return AMARILLO_CLARO
    else:
        return ROJO_CLARO

def get_color_text_mejora(mejora):
    """Color de texto según nivel de mejora"""
    if mejora >= 10:
        return VERDE
    elif mejora >= 5:
        return AZUL_MEJORA
    elif mejora >= 0:
        return AMARILLO
    else:
        return EPL_ROJO


# ============================================================
# CONSULTAS
# ============================================================
def fetch_mejora_data():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # --- Mejora por Grupo Operativo LOCAL: T1 vs T4 ---
    cur.execute("""
        WITH grupo_periodo AS (
            SELECT g.id, g.nombre,
                   p.codigo,
                   ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio,
                   COUNT(so.id) as evals,
                   COUNT(DISTINCT s.id) as sucursales
            FROM grupos_operativos g
            JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true AND s.clasificacion = 'local'
            JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            JOIN periodos_cas p ON so.periodo_id = p.id
            WHERE g.activo = true AND p.codigo IN ('T1-2025', 'T4-2025')
            GROUP BY g.id, g.nombre, p.codigo
        )
        SELECT t1.nombre, t1.promedio as prom_inicio, t4.promedio as prom_final,
               t4.promedio - t1.promedio as mejora,
               t1.evals as evals_inicio, t4.evals as evals_final,
               t1.sucursales as sucs_inicio, t4.sucursales as sucs_final
        FROM grupo_periodo t1
        JOIN grupo_periodo t4 ON t1.id = t4.id AND t4.codigo = 'T4-2025'
        WHERE t1.codigo = 'T1-2025'
        ORDER BY mejora DESC
    """)
    grupos_locales = cur.fetchall()

    # --- Mejora por Grupo Operativo FORÁNEO: S1 vs S2 ---
    cur.execute("""
        WITH grupo_periodo AS (
            SELECT g.id, g.nombre,
                   p.codigo,
                   ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio,
                   COUNT(so.id) as evals,
                   COUNT(DISTINCT s.id) as sucursales
            FROM grupos_operativos g
            JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true AND s.clasificacion = 'foraneo'
            JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            JOIN periodos_cas p ON so.periodo_id = p.id
            WHERE g.activo = true AND p.codigo IN ('S1-2025', 'S2-2025')
            GROUP BY g.id, g.nombre, p.codigo
        )
        SELECT s1.nombre, s1.promedio as prom_inicio, s2.promedio as prom_final,
               s2.promedio - s1.promedio as mejora,
               s1.evals as evals_inicio, s2.evals as evals_final,
               s1.sucursales as sucs_inicio, s2.sucursales as sucs_final
        FROM grupo_periodo s1
        JOIN grupo_periodo s2 ON s1.id = s2.id AND s2.codigo = 'S2-2025'
        WHERE s1.codigo = 'S1-2025'
        ORDER BY mejora DESC
    """)
    grupos_foraneos = cur.fetchall()

    # --- Mejora por Sucursal LOCAL: T1 vs T4 ---
    cur.execute("""
        WITH suc_periodo AS (
            SELECT s.id, s.nombre, g.nombre as grupo,
                   p.codigo,
                   ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio
            FROM sucursales s
            JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            JOIN periodos_cas p ON so.periodo_id = p.id
            WHERE s.activo = true AND s.clasificacion = 'local' AND p.codigo IN ('T1-2025', 'T4-2025')
            GROUP BY s.id, s.nombre, g.nombre, p.codigo
        )
        SELECT t1.nombre, t1.grupo,
               t1.promedio as prom_inicio, t4.promedio as prom_final,
               t4.promedio - t1.promedio as mejora
        FROM suc_periodo t1
        JOIN suc_periodo t4 ON t1.id = t4.id AND t4.codigo = 'T4-2025'
        WHERE t1.codigo = 'T1-2025'
        ORDER BY mejora DESC
    """)
    sucs_locales = cur.fetchall()

    # --- Mejora por Sucursal FORANEA: S1 vs S2 ---
    cur.execute("""
        WITH suc_periodo AS (
            SELECT s.id, s.nombre, g.nombre as grupo,
                   p.codigo,
                   ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio
            FROM sucursales s
            JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            JOIN periodos_cas p ON so.periodo_id = p.id
            WHERE s.activo = true AND s.clasificacion = 'foraneo' AND p.codigo IN ('S1-2025', 'S2-2025')
            GROUP BY s.id, s.nombre, g.nombre, p.codigo
        )
        SELECT s1.nombre, s1.grupo,
               s1.promedio as prom_inicio, s2.promedio as prom_final,
               s2.promedio - s1.promedio as mejora
        FROM suc_periodo s1
        JOIN suc_periodo s2 ON s1.id = s2.id AND s2.codigo = 'S2-2025'
        WHERE s1.codigo = 'S1-2025'
        ORDER BY mejora DESC
    """)
    sucs_foraneas = cur.fetchall()

    # --- Tendencia completa por grupo local (T1-T4) ---
    cur.execute("""
        SELECT g.nombre,
               p.codigo,
               ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio
        FROM grupos_operativos g
        JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true AND s.clasificacion = 'local'
        JOIN supervisiones_operativas so ON s.id = so.sucursal_id
        JOIN periodos_cas p ON so.periodo_id = p.id
        WHERE g.activo = true AND p.codigo IN ('T1-2025', 'T2-2025', 'T3-2025', 'T4-2025')
        GROUP BY g.id, g.nombre, p.codigo, p.fecha_inicio
        ORDER BY g.nombre, p.fecha_inicio
    """)
    tendencia_locales_raw = cur.fetchall()

    tendencia_locales = {}
    for r in tendencia_locales_raw:
        if r['nombre'] not in tendencia_locales:
            tendencia_locales[r['nombre']] = {}
        tendencia_locales[r['nombre']][r['codigo']] = float(r['promedio'])

    # --- Tendencia completa por grupo foráneo (S1-S2) ---
    cur.execute("""
        SELECT g.nombre,
               p.codigo,
               ROUND(AVG(so.calificacion_general)::numeric, 2) as promedio
        FROM grupos_operativos g
        JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true AND s.clasificacion = 'foraneo'
        JOIN supervisiones_operativas so ON s.id = so.sucursal_id
        JOIN periodos_cas p ON so.periodo_id = p.id
        WHERE g.activo = true AND p.codigo IN ('S1-2025', 'S2-2025')
        GROUP BY g.id, g.nombre, p.codigo, p.fecha_inicio
        ORDER BY g.nombre, p.fecha_inicio
    """)
    tendencia_foraneos_raw = cur.fetchall()

    tendencia_foraneos = {}
    for r in tendencia_foraneos_raw:
        if r['nombre'] not in tendencia_foraneos:
            tendencia_foraneos[r['nombre']] = {}
        tendencia_foraneos[r['nombre']][r['codigo']] = float(r['promedio'])

    conn.close()
    return {
        'grupos_locales': grupos_locales,
        'grupos_foraneos': grupos_foraneos,
        'sucs_locales': sucs_locales,
        'sucs_foraneas': sucs_foraneas,
        'tendencia_locales': tendencia_locales,
        'tendencia_foraneos': tendencia_foraneos,
    }


# ============================================================
# GENERACIÓN DEL PDF
# ============================================================
def build_pdf(data):
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
        fontSize=15, textColor=EPL_ROJO_OSCURO, alignment=TA_LEFT,
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
    info = ParagraphStyle(
        'Info', parent=styles['Normal'],
        fontSize=9, textColor=EPL_GRIS, fontName='Helvetica',
    )
    leyenda_style = ParagraphStyle(
        'Leyenda', parent=styles['Normal'],
        fontSize=7, textColor=EPL_GRIS,
    )

    elements = []

    # ============================================================
    # PORTADA
    # ============================================================
    elements.append(Spacer(1, 1.8*inch))

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
    elements.append(Paragraph("PREMIO A LA MAYOR MEJORA 2025", style_cover_sub))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Supervisión Operativa — CAS", style_subtitle))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Convención de la Marca", style_subtitle))

    elements.append(Spacer(1, 30))

    d2 = Drawing(500, 4)
    d2.add(Rect(0, 0, 500, 4, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d2)

    elements.append(Spacer(1, 40))

    style_dato = ParagraphStyle(
        'Dato', parent=styles['Normal'],
        fontSize=12, textColor=EPL_GRIS, alignment=TA_CENTER,
        fontName='Helvetica', spaceAfter=6,
    )

    n_gl = len(data['grupos_locales'])
    n_gf = len(data['grupos_foraneos'])
    n_sl = len(data['sucs_locales'])
    n_sf = len(data['sucs_foraneas'])

    elements.append(Paragraph(
        f"{n_gl + n_gf} Grupos Operativos Evaluados  |  {n_sl + n_sf} Sucursales Comparadas",
        style_dato
    ))
    elements.append(Paragraph(
        f"Locales: T1 vs T4 (Trimestral)  |  Foráneas: S1 vs S2 (Semestral)",
        style_dato
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Período: Año 2025", style_dato))

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y')}",
        style_footer
    ))
    elements.append(Paragraph("RDG Consultores — Confidencial", style_footer))

    elements.append(PageBreak())

    # ============================================================
    # HELPER: Tabla de mejora para grupos
    # ============================================================
    def make_grupo_mejora_table(items, periodo_inicio, periodo_final):
        header = ['Pos', 'Grupo Operativo', periodo_inicio, periodo_final, 'Mejora', 'Evals']
        col_widths = [0.4*inch, 2.5*inch, 0.95*inch, 0.95*inch, 0.95*inch, 0.8*inch]

        table_data = [header]
        for i, item in enumerate(items):
            mejora = float(item['mejora'])
            signo = '+' if mejora >= 0 else ''
            row = [
                str(i + 1),
                item['nombre'],
                f"{float(item['prom_inicio']):.2f}%",
                f"{float(item['prom_final']):.2f}%",
                f"{signo}{mejora:.2f}pp",
                f"{item['evals_inicio']}/{item['evals_final']}",
            ]
            table_data.append(row)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), BLANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ]

        for i, item in enumerate(items):
            row_idx = i + 1
            mejora = float(item['mejora'])
            bg = get_color_mejora(mejora)
            style_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

            # Columna de mejora con color de texto
            tc = get_color_text_mejora(mejora)
            style_cmds.append(('TEXTCOLOR', (4, row_idx), (4, row_idx), tc))
            style_cmds.append(('FONTNAME', (4, row_idx), (4, row_idx), 'Helvetica-Bold'))

            # Top 3 resaltado
            if i < 3:
                style_cmds.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
                if i == 0:
                    style_cmds.append(('TEXTCOLOR', (0, row_idx), (0, row_idx), EPL_DORADO))
                    style_cmds.append(('FONTSIZE', (0, row_idx), (0, row_idx), 10))

        table.setStyle(TableStyle(style_cmds))
        return table

    # ============================================================
    # HELPER: Tabla de mejora para sucursales
    # ============================================================
    def make_sucursal_mejora_table(items, periodo_inicio, periodo_final):
        header = ['Pos', 'Sucursal', 'Grupo', periodo_inicio, periodo_final, 'Mejora']
        col_widths = [0.35*inch, 1.8*inch, 1.7*inch, 0.85*inch, 0.85*inch, 0.85*inch]

        table_data = [header]
        for i, item in enumerate(items):
            mejora = float(item['mejora'])
            signo = '+' if mejora >= 0 else ''
            row = [
                str(i + 1),
                item['nombre'],
                item['grupo'],
                f"{float(item['prom_inicio']):.2f}%",
                f"{float(item['prom_final']):.2f}%",
                f"{signo}{mejora:.2f}pp",
            ]
            table_data.append(row)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), BLANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('TOPPADDING', (0, 1), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 2.5),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (3, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ]

        for i, item in enumerate(items):
            row_idx = i + 1
            mejora = float(item['mejora'])
            bg = get_color_mejora(mejora)
            style_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))

            tc = get_color_text_mejora(mejora)
            style_cmds.append(('TEXTCOLOR', (5, row_idx), (5, row_idx), tc))
            style_cmds.append(('FONTNAME', (5, row_idx), (5, row_idx), 'Helvetica-Bold'))

            if i < 3:
                style_cmds.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
                if i == 0:
                    style_cmds.append(('TEXTCOLOR', (0, row_idx), (0, row_idx), EPL_DORADO))
                    style_cmds.append(('FONTSIZE', (0, row_idx), (0, row_idx), 10))

        table.setStyle(TableStyle(style_cmds))
        return table

    # ============================================================
    # HELPER: Línea roja decorativa
    # ============================================================
    def red_line():
        d = Drawing(500, 2)
        d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
        return d

    # ============================================================
    # PÁGINA 2: MEJORA POR GRUPO OPERATIVO LOCAL
    # ============================================================
    elements.append(Paragraph("MAYOR MEJORA — GRUPOS OPERATIVOS LOCALES", style_section))
    elements.append(red_line())
    elements.append(Spacer(1, 4))

    gl = data['grupos_locales']
    elements.append(Paragraph(
        f"<b>{len(gl)}</b> grupos con datos en T1 y T4  |  "
        f"Comparación: Q1 2025 (Mar-Abr) vs Q4 2025 (Oct-Dic)",
        info
    ))
    elements.append(Spacer(1, 8))
    elements.append(make_grupo_mejora_table(gl, 'Q1 2025', 'Q4 2025'))

    # Ganador destacado
    if gl:
        ganador = gl[0]
        elements.append(Spacer(1, 12))
        style_ganador = ParagraphStyle(
            'Ganador', parent=styles['Normal'],
            fontSize=11, textColor=VERDE, alignment=TA_CENTER,
            fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=4,
        )
        mejora_g = float(ganador['mejora'])
        elements.append(Paragraph(
            f"GANADOR: {ganador['nombre']} — Mejora de +{mejora_g:.2f} puntos porcentuales",
            style_ganador
        ))
        elements.append(Paragraph(
            f"De {float(ganador['prom_inicio']):.2f}% en Q1 a {float(ganador['prom_final']):.2f}% en Q4",
            ParagraphStyle('GanadorSub', parent=info, alignment=TA_CENTER)
        ))

    # Tendencia completa locales
    if data['tendencia_locales']:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph("Tendencia Trimestral Completa (Locales)", style_obs_title))
        elements.append(Spacer(1, 4))

        periodos_t = ['T1-2025', 'T2-2025', 'T3-2025', 'T4-2025']
        t_header = ['Grupo Operativo', 'T1', 'T2', 'T3', 'T4']
        t_widths = [2.5*inch, 0.85*inch, 0.85*inch, 0.85*inch, 0.85*inch]
        t_data = [t_header]

        # Ordenar por mejora (T1 vs T4)
        sorted_grupos = sorted(
            data['tendencia_locales'].items(),
            key=lambda x: (x[1].get('T4-2025', 0) - x[1].get('T1-2025', 0)),
            reverse=True
        )

        for nombre, periodos in sorted_grupos:
            row = [nombre]
            for p in periodos_t:
                val = periodos.get(p)
                row.append(f"{val:.2f}%" if val is not None else '-')
            t_data.append(row)

        t_table = Table(t_data, colWidths=t_widths, repeatRows=1)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), BLANCO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('TOPPADDING', (0, 1), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ]
        t_table.setStyle(TableStyle(t_style))
        elements.append(t_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> Mejora ≥10pp  '
        '<font color="#1565C0">■</font> Mejora 5-9pp  '
        '<font color="#F9A825">■</font> Mejora 0-4pp  '
        '<font color="#C41E3A">■</font> Retroceso',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 3: MEJORA POR GRUPO OPERATIVO FORÁNEO
    # ============================================================
    elements.append(Paragraph("MAYOR MEJORA — GRUPOS OPERATIVOS FORÁNEOS", style_section))
    elements.append(red_line())
    elements.append(Spacer(1, 4))

    gf = data['grupos_foraneos']
    elements.append(Paragraph(
        f"<b>{len(gf)}</b> grupos con datos en S1 y S2  |  "
        f"Comparación: S1 2025 (Abr-Jun) vs S2 2025 (Jul-Nov)",
        info
    ))
    elements.append(Spacer(1, 8))
    elements.append(make_grupo_mejora_table(gf, 'S1 2025', 'S2 2025'))

    if gf:
        ganador_f = gf[0]
        elements.append(Spacer(1, 12))
        mejora_gf = float(ganador_f['mejora'])
        elements.append(Paragraph(
            f"GANADOR: {ganador_f['nombre']} — Mejora de +{mejora_gf:.2f} puntos porcentuales",
            style_ganador
        ))
        elements.append(Paragraph(
            f"De {float(ganador_f['prom_inicio']):.2f}% en S1 a {float(ganador_f['prom_final']):.2f}% en S2",
            ParagraphStyle('GanadorSub2', parent=info, alignment=TA_CENTER)
        ))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> Mejora ≥10pp  '
        '<font color="#1565C0">■</font> Mejora 5-9pp  '
        '<font color="#F9A825">■</font> Mejora 0-4pp  '
        '<font color="#C41E3A">■</font> Retroceso',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 4: MEJORA POR SUCURSAL LOCAL
    # ============================================================
    elements.append(Paragraph("MAYOR MEJORA — SUCURSALES LOCALES", style_section))
    elements.append(red_line())
    elements.append(Spacer(1, 4))

    sl = data['sucs_locales']
    elements.append(Paragraph(
        f"<b>{len(sl)}</b> sucursales con datos en T1 y T4  |  "
        f"Comparación: Q1 2025 vs Q4 2025",
        info
    ))
    elements.append(Spacer(1, 8))
    elements.append(make_sucursal_mejora_table(sl, 'Q1', 'Q4'))

    if sl:
        ganador_sl = sl[0]
        elements.append(Spacer(1, 10))
        mejora_sl = float(ganador_sl['mejora'])
        elements.append(Paragraph(
            f"GANADOR: {ganador_sl['nombre']} ({ganador_sl['grupo']}) — +{mejora_sl:.2f}pp",
            style_ganador
        ))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> Mejora ≥10pp  '
        '<font color="#1565C0">■</font> Mejora 5-9pp  '
        '<font color="#F9A825">■</font> Mejora 0-4pp  '
        '<font color="#C41E3A">■</font> Retroceso',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 5: MEJORA POR SUCURSAL FORANEA
    # ============================================================
    elements.append(Paragraph("MAYOR MEJORA — SUCURSALES FORÁNEAS", style_section))
    elements.append(red_line())
    elements.append(Spacer(1, 4))

    sf = data['sucs_foraneas']
    elements.append(Paragraph(
        f"<b>{len(sf)}</b> sucursales con datos en S1 y S2  |  "
        f"Comparación: S1 2025 vs S2 2025",
        info
    ))
    elements.append(Spacer(1, 8))
    elements.append(make_sucursal_mejora_table(sf, 'S1', 'S2'))

    if sf:
        ganador_sf = sf[0]
        elements.append(Spacer(1, 10))
        mejora_sf = float(ganador_sf['mejora'])
        elements.append(Paragraph(
            f"GANADOR: {ganador_sf['nombre']} ({ganador_sf['grupo']}) — +{mejora_sf:.2f}pp",
            style_ganador
        ))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '<font color="#1B7A3D">■</font> Mejora ≥10pp  '
        '<font color="#1565C0">■</font> Mejora 5-9pp  '
        '<font color="#F9A825">■</font> Mejora 0-4pp  '
        '<font color="#C41E3A">■</font> Retroceso',
        leyenda_style
    ))

    elements.append(PageBreak())

    # ============================================================
    # PÁGINA 6: RESUMEN Y OBSERVACIONES
    # ============================================================
    elements.append(Paragraph("RESUMEN DE GANADORES Y METODOLOGÍA", style_section))
    elements.append(red_line())
    elements.append(Spacer(1, 12))

    # Tabla resumen de ganadores
    resumen_header = ['Premio', 'Ganador', 'Mejora', 'Inicio', 'Final']
    resumen_widths = [2.0*inch, 2.0*inch, 0.8*inch, 0.8*inch, 0.8*inch]
    resumen_data = [resumen_header]

    premios = [
        ('Mejor Grupo Local', data['grupos_locales'], 'T1→T4'),
        ('Mejor Grupo Foráneo', data['grupos_foraneos'], 'S1→S2'),
        ('Mejor Sucursal Local', data['sucs_locales'], 'T1→T4'),
        ('Mejor Sucursal Foránea', data['sucs_foraneas'], 'S1→S2'),
    ]

    for titulo, items, periodo in premios:
        if items:
            g = items[0]
            mejora = float(g['mejora'])
            resumen_data.append([
                titulo,
                g['nombre'],
                f"+{mejora:.2f}pp",
                f"{float(g['prom_inicio']):.2f}%",
                f"{float(g['prom_final']):.2f}%",
            ])

    resumen_table = Table(resumen_data, colWidths=resumen_widths, repeatRows=1)
    resumen_style = [
        ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
        ('TEXTCOLOR', (0, 0), (-1, 0), BLANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (2, 1), (2, -1), VERDE),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ('BACKGROUND', (0, 1), (-1, -1), VERDE_CLARO),
    ]
    resumen_table.setStyle(TableStyle(resumen_style))
    elements.append(resumen_table)

    elements.append(Spacer(1, 20))

    # Observaciones
    elements.append(Paragraph("Metodología", style_obs_title))
    elements.append(Paragraph(
        "El premio a la <b>Mayor Mejora</b> se determina comparando la calificación promedio "
        "de la Supervisión Operativa entre el <b>primer periodo</b> y el <b>último periodo</b> del año 2025. "
        "Para sucursales y grupos <b>locales</b> se compara T1 (Q1, Mar-Abr) vs T4 (Q4, Oct-Dic). "
        "Para sucursales y grupos <b>foráneos</b> se compara S1 (Abr-Jun) vs S2 (Jul-Nov). "
        "La mejora se expresa en <b>puntos porcentuales (pp)</b>.",
        style_obs
    ))

    elements.append(Paragraph("Elegibilidad", style_obs_title))
    elements.append(Paragraph(
        f"Solo participan los grupos y sucursales que fueron evaluados en <b>ambos periodos</b> "
        f"de comparación. Locales: <b>{len(data['sucs_locales'])}</b> sucursales y "
        f"<b>{len(data['grupos_locales'])}</b> grupos elegibles. "
        f"Foráneos: <b>{len(data['sucs_foraneas'])}</b> sucursales y "
        f"<b>{len(data['grupos_foraneos'])}</b> grupos elegibles.",
        style_obs
    ))

    elements.append(Paragraph("Interpretación", style_obs_title))
    elements.append(Paragraph(
        "Una mejora alta indica que el grupo o sucursal mostró un <b>progreso significativo</b> "
        "durante el año. Los grupos o sucursales que empezaron con calificaciones bajas y terminaron "
        "con calificaciones altas demuestran el mayor esfuerzo de cambio. "
        "Este premio reconoce el <b>esfuerzo de mejora continua</b>, no la calificación absoluta.",
        style_obs
    ))

    elements.append(Paragraph("Nota sobre Grupos con 1 Sucursal", style_obs_title))
    elements.append(Paragraph(
        "Algunos grupos operativos cuentan con una sola sucursal evaluada en la categoría "
        "(como GRUPO SABINAS HIDALGO, GRUPO CENTRITO y GRUPO PIEDRAS NEGRAS). "
        "En estos casos, la mejora del grupo es idéntica a la mejora de su sucursal. "
        "Todos los grupos son elegibles independientemente de su tamaño.",
        style_obs
    ))

    # Pie
    elements.append(Spacer(1, 0.5*inch))
    d = Drawing(500, 1)
    d.add(Rect(0, 0, 500, 1, fillColor=colors.HexColor('#CCCCCC'), strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "El Pollo Loco México — Sistema CAS — "
        f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')} — RDG Consultores — Confidencial",
        style_footer
    ))

    doc.build(elements)
    print(f"\nPDF generado: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print("Obteniendo datos de mejora 2025...")
    data = fetch_mejora_data()

    print(f"  Grupos locales:    {len(data['grupos_locales'])} (T1 vs T4)")
    print(f"  Grupos foráneos:   {len(data['grupos_foraneos'])} (S1 vs S2)")
    print(f"  Sucursales locales:  {len(data['sucs_locales'])} (T1 vs T4)")
    print(f"  Sucursales foráneas: {len(data['sucs_foraneas'])} (S1 vs S2)")

    print("\n--- GANADORES ---")
    if data['grupos_locales']:
        g = data['grupos_locales'][0]
        print(f"  Mejor Grupo Local:      {g['nombre']} (+{float(g['mejora']):.2f}pp)")
    if data['grupos_foraneos']:
        g = data['grupos_foraneos'][0]
        print(f"  Mejor Grupo Foráneo:    {g['nombre']} (+{float(g['mejora']):.2f}pp)")
    if data['sucs_locales']:
        s = data['sucs_locales'][0]
        print(f"  Mejor Sucursal Local:   {s['nombre']} - {s['grupo']} (+{float(s['mejora']):.2f}pp)")
    if data['sucs_foraneas']:
        s = data['sucs_foraneas'][0]
        print(f"  Mejor Sucursal Foránea: {s['nombre']} - {s['grupo']} (+{float(s['mejora']):.2f}pp)")

    print("\nGenerando PDF...")
    build_pdf(data)
    print("Listo!")
