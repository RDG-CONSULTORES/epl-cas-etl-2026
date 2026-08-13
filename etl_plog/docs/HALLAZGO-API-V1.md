# Hallazgo API Zenput v1 (2026-08-13)

Roberto: "v1 funciona, trae endpoints interesantes". Verificado empíricamente + busqué en todos los proyectos locales (el-pollo-loco-zenput-etl, zenput_etl, zenput-api-project, etc.) y en epl-gpt/docs/zenput.

## Veredicto: v1 está MAYORMENTE retirado, PERO 2 endpoints siguen VIVOS y útiles
Auth idéntica a v3: header `X-API-TOKEN` (no hay auth alterna que desbloquee más — probado Bearer=403). Base `https://www.zenput.com/api/v1/`. Estructura de respuesta distinta: `{success, status, results/message}` (v3 usa `{meta, data}`).

### ✅ VIVOS
| Endpoint v1 | Qué hace | Útil para |
|---|---|---|
| `forms/list_templates/?limit=200` | Catálogo de formularios con **metadata que v3 estructura distinto**: category_id/category_name, creator_full_name, permission_id, is_shared_form, num_submissions, date_last_submitted, is_secure | Descubrimiento/categorización de formularios; saber quién creó cada form y su categoría |
| `forms/get/{submission_id}?output=pdf` | **Genera el PDF del formulario llenado** (usa el id hex de v3; responde "PDF generator launched, email on its way" — async por correo) | **Evidencia/auditoría: bajar el formulario real como PDF** para reportes o inspecciones |

### ❌ MUERTOS (404 / 410 Gone)
`forms/list/{template}` (410 Gone) · `forms/template/{id}` · `forms/get/{id}/` (sin output) · `forms/get_template/` · `submissions/`, `locations/`, `users/`, `teams/`, `reports/`, `scores/`, `projects/`, `tasks/`, `accounts/` — todos 404.

## Lo interesante para nosotros
1. **PDF de submission** (`forms/get/{id}?output=pdf`): capacidad real que v3 NO tiene. Un director podría recibir el formulario llenado en PDF (evidencia). Limitación: es async por correo, no descarga directa — habría que ver si hay variante síncrona.
2. **Metadata de plantillas** (`list_templates`): categorías y creador — podría enriquecer el admin (agrupar formularios por categoría).

## Pendiente
Deep research en curso (wf_b7d4fa76-59b) sobre capacidades documentadas de v1/v2/v3 y endpoints que no usamos (scores agregados, field schemas, webhooks, export masivo).
