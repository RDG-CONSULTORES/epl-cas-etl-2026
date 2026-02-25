#!/usr/bin/env python3
"""
EPL CAS 2025 - Comparativo Protección Civil
Chapultepec vs Aztlán - Detalle de las 4 supervisiones de seguridad
Extrae preguntas, respuestas y fotos de la API de Zenput
"""

import os
import requests
import json
from datetime import datetime
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================
ZENPUT_TOKEN = os.environ['ZENPUT_TOKEN']
ZENPUT_BASE = 'https://www.zenput.com/api/v3'
HEADERS = {'X-API-TOKEN': ZENPUT_TOKEN}

OUTPUT_FILE = '/Users/robertodavila/epl-cas-etl-2026/EPL_CAS_2025_Comparativo_Proteccion_Civil.pdf'
PHOTO_DIR = '/Users/robertodavila/epl-cas-etl-2026/fotos_proteccion_civil'

# Submission IDs de seguridad 2025
SUBMISSIONS = {
    'Chapultepec': {
        'Q1': '67ddb55a074c5bc11811a1f9',
        'Q2': '686587162fea84a28a30a2e3',
        'Q3': '68b5efffb110dcfe344d9233',
        'Q4': '6920bb2973c80a592439078e',
    },
    'Aztlán': {
        'Q1': '67ed818450e6355a4616f549',
        'Q2': '68753801f2b3bafc5a401c1f',
        'Q3': '68bb2e2050afdb5d37987154',
        'Q4': '6924ad1fc34e8f27194352cd',
    }
}

# Preguntas de Protección Civil (orden en el formulario)
PREGUNTAS_PC = [
    {'num': 39, 'titulo': 'Programa Interno de Protección Civil Vigente', 'key': 'programa_pc'},
    {'num': 40, 'titulo': 'Prueba de Hermeticidad Vigente', 'key': 'hermeticidad'},
    {'num': 41, 'titulo': 'Comprobante de Extintores Vigentes', 'key': 'extintores'},
    {'num': 42, 'titulo': 'Reporte de Fumigación Vigente', 'key': 'fumigacion'},
    {'num': 43, 'titulo': 'Dictamen Eléctrico', 'key': 'dictamen_electrico'},
    {'num': 44, 'titulo': 'Dictamen Estructural', 'key': 'dictamen_estructural'},
]

# Colores
EPL_ROJO = colors.HexColor('#C41E3A')
EPL_ROJO_OSCURO = colors.HexColor('#8B0000')
EPL_DORADO = colors.HexColor('#D4A017')
EPL_GRIS = colors.HexColor('#4A4A4A')
VERDE = colors.HexColor('#1B7A3D')
VERDE_CLARO = colors.HexColor('#E8F5E9')
ROJO_CLARO = colors.HexColor('#FFEBEE')
GRIS_CLARO = colors.HexColor('#F5F5F5')

# ============================================================
# FETCH DATA FROM ZENPUT API
# ============================================================
def fetch_submission(sub_id, form_id=877139):
    """Fetch a single submission from Zenput API"""
    # The v3 list endpoint with ID filter
    # Need to search through results since direct get by ID doesn't work
    resp = requests.get(f'{ZENPUT_BASE}/submissions/', headers=HEADERS,
        params={'form_template_id': form_id, 'limit': 100}, timeout=60)

    if resp.status_code != 200:
        print(f"  ERROR: {resp.status_code}")
        return None

    data = resp.json()
    for sub in data.get('data', []):
        if sub['id'] == sub_id:
            return sub

    # If not found in first page, try with date filters
    return None

def fetch_all_submissions():
    """Fetch all 8 submissions efficiently"""
    print("Descargando submissions de Zenput API...")

    # Collect all IDs we need
    all_ids = {}
    for suc, periodos in SUBMISSIONS.items():
        for periodo, sub_id in periodos.items():
            all_ids[sub_id] = (suc, periodo)

    found = {}
    offset = 0

    while len(found) < len(all_ids):
        print(f"  Fetching offset={offset}...")
        resp = requests.get(f'{ZENPUT_BASE}/submissions/', headers=HEADERS,
            params={'form_template_id': 877139, 'limit': 100, 'offset': offset}, timeout=60)

        if resp.status_code != 200:
            print(f"  ERROR: {resp.status_code}")
            break

        data = resp.json().get('data', [])
        if not data:
            break

        for sub in data:
            if sub['id'] in all_ids:
                suc, periodo = all_ids[sub['id']]
                found[sub['id']] = {
                    'sucursal': suc,
                    'periodo': periodo,
                    'data': sub
                }
                print(f"  Found: {suc} {periodo} ({sub['id']})")

        if len(data) < 100:
            break
        offset += 100

    print(f"  Total encontrados: {len(found)}/{len(all_ids)}")
    return found

def extract_proteccion_civil(submission_data):
    """Extract Proteccion Civil section from a submission"""
    answers = submission_data.get('answers', [])
    meta = submission_data.get('smetadata', {})

    result = {
        'fecha': meta.get('date_submitted', ''),
        'supervisor': meta.get('created_by', {}).get('display_name', ''),
        'calificacion_general': None,
        'pc_puntos_max': None,
        'pc_puntos': None,
        'pc_porcentaje': None,
        'preguntas': [],
    }

    # Find the Proteccion Civil section
    in_pc_section = False

    for ans in answers:
        title = (ans.get('title') or '').strip()
        ftype = ans.get('field_type', '')
        value = ans.get('value')

        # Track section
        if ftype == 'section':
            in_pc_section = 'PROTECCION CIVIL' in title.upper() or 'PROTECCIÓN CIVIL' in title.upper()
            continue

        # General calificacion
        if ftype == 'formula' and title.upper() in ['CALIFICACION PORCENTAJE %', 'CALIFICACIÓN PORCENTAJE %']:
            result['calificacion_general'] = value

        if not in_pc_section:
            continue

        # Proteccion Civil fields
        if ftype == 'yesno':
            # Zenput returns "true"/"false" strings, normalize to bool
            if isinstance(value, str):
                resp_bool = value.lower() == 'true'
            else:
                resp_bool = bool(value)
            pregunta = {
                'titulo': title,
                'respuesta': resp_bool,
                'foto_key': None,
                'vigencia': None,
            }
            result['preguntas'].append(pregunta)

        elif ftype == 'image':
            # Attach photo to last yesno question
            if result['preguntas']:
                if isinstance(value, list) and len(value) > 0:
                    result['preguntas'][-1]['foto_key'] = value[0].get('s3_key', '')
                elif isinstance(value, str) and value:
                    result['preguntas'][-1]['foto_key'] = value

        elif ftype == 'datetime':
            # Attach vigencia to last yesno question
            if result['preguntas']:
                result['preguntas'][-1]['vigencia'] = value

        elif ftype == 'formula':
            t = title.upper()
            if 'MAX' in t or 'MAXIMO' in t or 'MÁXIMO' in t:
                result['pc_puntos_max'] = value
            elif 'TOTAL' in t and 'PORCENTAJE' not in t:
                result['pc_puntos'] = value
            elif 'PORCENTAJE' in t:
                result['pc_porcentaje'] = value

    return result

def download_photo(s3_key, filename):
    """Download photo from Zenput storage API"""
    if not s3_key:
        return None

    filepath = os.path.join(PHOTO_DIR, filename)
    if os.path.exists(filepath):
        return filepath

    try:
        resp = requests.get(
            'https://www.zenput.com/api/v2/users/current/storage/',
            headers=HEADERS,
            params={'path': s3_key},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            # Get the signed URL (Zenput returns it in data.location)
            url = data.get('data', {}).get('location', '') or data.get('url') or data.get('signed_url', '')
            if url:
                img_resp = requests.get(url, timeout=30)
                if img_resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(img_resp.content)
                    return filepath
    except Exception as e:
        print(f"  Error downloading photo: {e}")

    return None

# ============================================================
# GENERATE PDF
# ============================================================
def build_pdf(all_data):
    doc = SimpleDocTemplate(
        OUTPUT_FILE,
        pagesize=letter,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle('Title2', parent=styles['Title'],
        fontSize=22, textColor=EPL_ROJO_OSCURO, alignment=TA_CENTER,
        fontName='Helvetica-Bold', spaceAfter=4)
    style_subtitle = ParagraphStyle('Sub2', parent=styles['Normal'],
        fontSize=12, textColor=EPL_GRIS, alignment=TA_CENTER, fontName='Helvetica', spaceAfter=4)
    style_section = ParagraphStyle('Sec2', parent=styles['Heading1'],
        fontSize=14, textColor=EPL_ROJO_OSCURO, fontName='Helvetica-Bold',
        spaceBefore=8, spaceAfter=6, borderWidth=0, borderPadding=0)
    style_subsec = ParagraphStyle('SubSec', parent=styles['Heading2'],
        fontSize=11, textColor=EPL_ROJO_OSCURO, fontName='Helvetica-Bold',
        spaceBefore=6, spaceAfter=4)
    style_normal = ParagraphStyle('Norm', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#333333'), fontName='Helvetica', leading=12)
    style_small = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=7.5, textColor=EPL_GRIS, fontName='Helvetica', leading=10)
    style_footer = ParagraphStyle('Foot', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)

    elements = []

    # ============================================================
    # PORTADA
    # ============================================================
    elements.append(Spacer(1, 1.5*inch))
    d = Drawing(500, 4)
    d.add(Rect(0, 0, 500, 4, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("COMPARATIVO PROTECCIÓN CIVIL", style_title))
    elements.append(Paragraph("Supervisión de Seguridad 2025", style_subtitle))
    elements.append(Spacer(1, 8))

    style_gold = ParagraphStyle('Gold', parent=style_subtitle,
        fontSize=16, textColor=EPL_DORADO, fontName='Helvetica-Bold')
    elements.append(Paragraph("21 - Chapultepec  vs  14 - Aztlán", style_gold))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Sección X. Programa Interno Protección Civil", style_subtitle))
    elements.append(Paragraph("Detalle pregunta por pregunta — 4 trimestres", style_subtitle))

    elements.append(Spacer(1, 25))
    d2 = Drawing(500, 4)
    d2.add(Rect(0, 0, 500, 4, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d2)

    elements.append(Spacer(1, 30))
    style_dato = ParagraphStyle('Dato', parent=styles['Normal'],
        fontSize=11, textColor=EPL_GRIS, alignment=TA_CENTER, fontName='Helvetica', spaceAfter=4)
    elements.append(Paragraph("6 Preguntas evaluadas por supervisión:", style_dato))
    elements.append(Paragraph(
        "Programa PC  |  Hermeticidad  |  Extintores  |  Fumigación  |  Dictamen Eléctrico  |  Dictamen Estructural",
        ParagraphStyle('Items', parent=style_dato, fontSize=9)))

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d de Febrero de 2026')}",
        style_footer))
    elements.append(Paragraph("RDG Consultores — Confidencial", style_footer))
    elements.append(PageBreak())

    # ============================================================
    # RESUMEN COMPARATIVO
    # ============================================================
    elements.append(Paragraph("RESUMEN COMPARATIVO — PROTECCIÓN CIVIL", style_section))
    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 8))

    # Tabla resumen
    header = ['Periodo', 'Chapultepec\nCalif. Gral', 'Chapultepec\nProt. Civil',
              'Aztlán\nCalif. Gral', 'Aztlán\nProt. Civil', 'Diferencia\nProt. Civil']

    table_data = [header]

    for periodo in ['Q1', 'Q2', 'Q3', 'Q4']:
        chap = all_data.get(('Chapultepec', periodo), {})
        azt = all_data.get(('Aztlán', periodo), {})

        chap_gral = chap.get('calificacion_general', '-')
        chap_pc = chap.get('pc_porcentaje', '-')
        azt_gral = azt.get('calificacion_general', '-')
        azt_pc = azt.get('pc_porcentaje', '-')

        chap_gral_s = f"{chap_gral}%" if chap_gral and chap_gral != '-' else '-'
        chap_pc_s = f"{chap_pc}%" if chap_pc and chap_pc != '-' else '-'
        azt_gral_s = f"{azt_gral}%" if azt_gral and azt_gral != '-' else '-'
        azt_pc_s = f"{azt_pc}%" if azt_pc and azt_pc != '-' else '-'

        diff = ''
        if isinstance(chap_pc, (int, float)) and isinstance(azt_pc, (int, float)):
            d_val = chap_pc - azt_pc
            if d_val > 0:
                diff = f"+{d_val:.2f}%"
            elif d_val < 0:
                diff = f"{d_val:.2f}%"
            else:
                diff = "EMPATE"

        table_data.append([periodo, chap_gral_s, chap_pc_s, azt_gral_s, azt_pc_s, diff])

    # Promedios
    chap_pcs = [all_data.get(('Chapultepec', p), {}).get('pc_porcentaje') for p in ['Q1','Q2','Q3','Q4']]
    azt_pcs = [all_data.get(('Aztlán', p), {}).get('pc_porcentaje') for p in ['Q1','Q2','Q3','Q4']]
    chap_pcs = [x for x in chap_pcs if x is not None]
    azt_pcs = [x for x in azt_pcs if x is not None]

    chap_avg = sum(chap_pcs)/len(chap_pcs) if chap_pcs else 0
    azt_avg = sum(azt_pcs)/len(azt_pcs) if azt_pcs else 0
    diff_avg = chap_avg - azt_avg
    diff_s = f"+{diff_avg:.2f}%" if diff_avg > 0 else (f"{diff_avg:.2f}%" if diff_avg < 0 else "EMPATE")

    table_data.append(['PROMEDIO', '', f"{chap_avg:.2f}%", '', f"{azt_avg:.2f}%", diff_s])

    t = Table(table_data, colWidths=[0.7*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.0*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        # Last row (promedio) bold
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), GRIS_CLARO),
        ('LINEABOVE', (0, -1), (-1, -1), 1, EPL_ROJO),
    ]))

    # Color code PC cells
    for row_idx in range(1, len(table_data)):
        for col_idx in [2, 4]:  # PC columns
            val_str = table_data[row_idx][col_idx]
            if '%' in val_str:
                val = float(val_str.replace('%', '').replace('+', ''))
                if val >= 100:
                    t.setStyle(TableStyle([('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), VERDE_CLARO)]))
                elif val < 100:
                    t.setStyle(TableStyle([('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), ROJO_CLARO)]))

    elements.append(t)
    elements.append(Spacer(1, 15))

    # ============================================================
    # DETALLE POR TRIMESTRE
    # ============================================================
    elements.append(Paragraph("DETALLE PREGUNTA POR PREGUNTA", style_section))
    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 8))

    for periodo in ['Q1', 'Q2', 'Q3', 'Q4']:
        chap = all_data.get(('Chapultepec', periodo), {})
        azt = all_data.get(('Aztlán', periodo), {})

        chap_fecha = chap.get('fecha', '')[:10] if chap.get('fecha') else '-'
        azt_fecha = azt.get('fecha', '')[:10] if azt.get('fecha') else '-'
        chap_sup = chap.get('supervisor', '-')
        azt_sup = azt.get('supervisor', '-')

        elements.append(Paragraph(
            f"<b>{periodo} 2025</b> — Chapultepec: {chap_fecha} ({chap_sup})  |  Aztlán: {azt_fecha} ({azt_sup})",
            style_subsec))

        # Tabla de detalle
        detail_header = ['#', 'Pregunta', 'Chapultepec', 'Aztlán']
        detail_data = [detail_header]

        chap_pregs = chap.get('preguntas', [])
        azt_pregs = azt.get('preguntas', [])

        for i, preg_def in enumerate(PREGUNTAS_PC):
            chap_resp = chap_pregs[i]['respuesta'] if i < len(chap_pregs) else None
            azt_resp = azt_pregs[i]['respuesta'] if i < len(azt_pregs) else None

            chap_vig = chap_pregs[i].get('vigencia', '') if i < len(chap_pregs) else ''
            azt_vig = azt_pregs[i].get('vigencia', '') if i < len(azt_pregs) else ''

            chap_text = 'SI' if chap_resp == True else ('NO' if chap_resp == False else '-')
            azt_text = 'SI' if azt_resp == True else ('NO' if azt_resp == False else '-')

            # Add vigencia if available
            if chap_vig and chap_vig != 'NULL':
                vig_date = str(chap_vig)[:10]
                chap_text += f"\nVig: {vig_date}"
            if azt_vig and azt_vig != 'NULL':
                vig_date = str(azt_vig)[:10]
                azt_text += f"\nVig: {vig_date}"

            detail_data.append([
                str(preg_def['num']),
                preg_def['titulo'],
                chap_text,
                azt_text,
            ])

        # Add score row
        chap_pc = chap.get('pc_porcentaje', '-')
        azt_pc = azt.get('pc_porcentaje', '-')
        chap_pts = f"{chap.get('pc_puntos', '?')}/{chap.get('pc_puntos_max', '?')}"
        azt_pts = f"{azt.get('pc_puntos', '?')}/{azt.get('pc_puntos_max', '?')}"

        detail_data.append([
            '', 'CALIFICACIÓN',
            f"{chap_pc}%\n({chap_pts} pts)" if chap_pc and chap_pc != '-' else '-',
            f"{azt_pc}%\n({azt_pts} pts)" if azt_pc and azt_pc != '-' else '-',
        ])

        dt = Table(detail_data, colWidths=[0.4*inch, 2.8*inch, 1.7*inch, 1.7*inch], repeatRows=1)

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), EPL_ROJO_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (3, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, EPL_ROJO),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            # Score row
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), GRIS_CLARO),
            ('LINEABOVE', (0, -1), (-1, -1), 1, EPL_ROJO),
        ]

        # Color cells based on SI/NO
        for row_idx in range(1, len(detail_data) - 1):  # skip header and score row
            for col_idx in [2, 3]:
                val = detail_data[row_idx][col_idx]
                if val.startswith('SI'):
                    style_cmds.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), VERDE_CLARO))
                    style_cmds.append(('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), VERDE))
                elif val.startswith('NO'):
                    style_cmds.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), ROJO_CLARO))
                    style_cmds.append(('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), EPL_ROJO))

        dt.setStyle(TableStyle(style_cmds))
        elements.append(dt)
        elements.append(Spacer(1, 12))

    # ============================================================
    # PÁGINA DE FOTOS
    # ============================================================
    elements.append(PageBreak())
    elements.append(Paragraph("EVIDENCIA FOTOGRÁFICA — DICTÁMENES", style_section))
    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "Fotos de evidencia de Dictamen Eléctrico y Dictamen Estructural extraídas de Zenput.",
        style_normal))
    elements.append(Spacer(1, 8))

    for periodo in ['Q1', 'Q2', 'Q3', 'Q4']:
        elements.append(Paragraph(f"<b>{periodo} 2025</b>", style_subsec))

        for suc_name in ['Chapultepec', 'Aztlán']:
            data = all_data.get((suc_name, periodo), {})
            preguntas = data.get('preguntas', [])

            # Dictamen Eléctrico (index 4) and Estructural (index 5)
            for idx, preg_name in [(4, 'Dictamen Eléctrico'), (5, 'Dictamen Estructural')]:
                if idx < len(preguntas):
                    preg = preguntas[idx]
                    resp = 'SI' if preg['respuesta'] == True else 'NO' if preg['respuesta'] == False else '-'
                    foto_path = preg.get('foto_local')

                    label = f"{suc_name} — {preg_name}: <b>{resp}</b>"
                    elements.append(Paragraph(label, style_small))

                    if foto_path and os.path.exists(foto_path):
                        try:
                            img = Image(foto_path, width=2.5*inch, height=2*inch)
                            img.hAlign = 'LEFT'
                            elements.append(img)
                        except Exception as e:
                            elements.append(Paragraph(f"[Error cargando imagen: {e}]", style_small))
                    else:
                        elements.append(Paragraph("[Sin foto disponible]", style_small))

                    elements.append(Spacer(1, 4))

        elements.append(Spacer(1, 6))

    # ============================================================
    # CONCLUSIONES
    # ============================================================
    elements.append(PageBreak())
    elements.append(Paragraph("CONCLUSIONES", style_section))
    d = Drawing(500, 2)
    d.add(Rect(0, 0, 500, 2, fillColor=EPL_ROJO, strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 10))

    style_conclusion = ParagraphStyle('Concl', parent=style_normal,
        fontSize=10, leading=14, spaceBefore=4, spaceAfter=8)

    # Build dynamic conclusions
    chap_scores = []
    azt_scores = []
    for p in ['Q1', 'Q2', 'Q3', 'Q4']:
        c = all_data.get(('Chapultepec', p), {})
        a = all_data.get(('Aztlán', p), {})
        if c.get('pc_porcentaje') is not None:
            chap_scores.append(c['pc_porcentaje'])
        if a.get('pc_porcentaje') is not None:
            azt_scores.append(a['pc_porcentaje'])

    chap_avg = sum(chap_scores)/len(chap_scores) if chap_scores else 0
    azt_avg = sum(azt_scores)/len(azt_scores) if azt_scores else 0

    chap_fallos = []
    azt_fallos = []
    for p in ['Q1', 'Q2', 'Q3', 'Q4']:
        for suc, fallos_list in [('Chapultepec', chap_fallos), ('Aztlán', azt_fallos)]:
            data = all_data.get((suc, p), {})
            for i, preg in enumerate(data.get('preguntas', [])):
                if preg['respuesta'] == False:
                    fallos_list.append(f"{PREGUNTAS_PC[i]['titulo']} ({p})")

    elements.append(Paragraph(
        f"<b>Chapultepec</b> obtiene un promedio de <b>{chap_avg:.2f}%</b> en Protección Civil vs "
        f"<b>{azt_avg:.2f}%</b> de <b>Aztlán</b>.",
        style_conclusion))

    if chap_fallos:
        elements.append(Paragraph(
            f"<b>Chapultepec</b> tuvo fallas en: {', '.join(chap_fallos)}.",
            style_conclusion))
    else:
        elements.append(Paragraph(
            "<b>Chapultepec</b> no tuvo fallas en Protección Civil durante 2025.",
            style_conclusion))

    if azt_fallos:
        elements.append(Paragraph(
            f"<b>Aztlán</b> tuvo fallas en: {', '.join(azt_fallos)}.",
            style_conclusion))
    else:
        elements.append(Paragraph(
            "<b>Aztlán</b> no tuvo fallas en Protección Civil durante 2025.",
            style_conclusion))

    elements.append(Paragraph(
        "Ambas sucursales lograron <b>100% en la Supervisión Operativa</b> en los 4 trimestres de 2025. "
        "La diferencia que define el 1er y 2do lugar se da exclusivamente en la "
        "<b>Supervisión de Seguridad</b>, donde la sección de Protección Civil es el factor determinante.",
        style_conclusion))

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    d = Drawing(500, 1)
    d.add(Rect(0, 0, 500, 1, fillColor=colors.HexColor('#CCCCCC'), strokeColor=None))
    elements.append(d)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "El Pollo Loco México — Sistema CAS — "
        f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')} — RDG Consultores — Confidencial",
        style_footer))

    doc.build(elements)
    print(f"\nPDF generado: {OUTPUT_FILE}")

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    os.makedirs(PHOTO_DIR, exist_ok=True)

    # 1. Fetch all submissions
    submissions = fetch_all_submissions()

    # 2. Extract Proteccion Civil data
    print("\nExtrayendo datos de Protección Civil...")
    all_data = {}

    for sub_id, info in submissions.items():
        suc = info['sucursal']
        periodo = info['periodo']
        pc_data = extract_proteccion_civil(info['data'])
        all_data[(suc, periodo)] = pc_data

        pts = pc_data.get('pc_puntos', '?')
        pts_max = pc_data.get('pc_puntos_max', '?')
        pct = pc_data.get('pc_porcentaje', '?')
        print(f"  {suc} {periodo}: {pts}/{pts_max} = {pct}% | Preguntas: {len(pc_data['preguntas'])}")

    # 3. Download photos (dictámenes)
    print("\nDescargando fotos de evidencia...")
    photo_count = 0
    for (suc, periodo), data in all_data.items():
        for i, preg in enumerate(data.get('preguntas', [])):
            if preg.get('foto_key'):
                filename = f"{suc}_{periodo}_P{PREGUNTAS_PC[i]['num']}_{PREGUNTAS_PC[i]['key']}.jpg"
                filepath = download_photo(preg['foto_key'], filename)
                preg['foto_local'] = filepath
                if filepath:
                    photo_count += 1
                    print(f"  Descargada: {filename}")
            else:
                preg['foto_local'] = None

    print(f"  Total fotos descargadas: {photo_count}")

    # 4. Generate PDF
    print("\nGenerando PDF comparativo...")
    build_pdf(all_data)
    print("Listo!")
