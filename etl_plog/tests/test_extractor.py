"""Tests del extractor de calificaciones (lógica pura, sin BD)."""
from etl_plog.calificaciones import extractor


def _fx(pares):
    """Construye un payload con formulas {titulo: valor}."""
    return {"answers": [{"title": t, "value": v, "field_type": "formula"} for t, v in pares.items()]}


class TestNum:
    def test_parsea_decimal(self):
        assert extractor._num("96.23") == 96.23

    def test_quita_porcentaje_y_comas(self):
        assert extractor._num("1,050%") == 1050.0

    def test_none_y_vacio(self):
        assert extractor._num(None) is None and extractor._num("") is None

    def test_no_numerico(self):
        assert extractor._num("N/A") is None


class TestClamp100:
    def test_bonus_se_recorta_a_100(self):
        spec = {"score_total": "Total (100%):", "areas": []}
        std, raw, _ = extractor.extraer_submission(_fx({"Total (100%):": 104.17}), spec)
        assert std == 100.0 and raw == 104.17

    def test_normal_no_se_toca(self):
        spec = {"score_total": "Total (100%):", "areas": []}
        std, raw, _ = extractor.extraer_submission(_fx({"Total (100%):": 86.4}), spec)
        assert std == 86.4 and raw == 86.4


class TestAreas:
    def test_extrae_pct_y_puntos(self):
        spec = {"score_total": "T", "areas": [
            {"area": "Marinado", "campo_pct": "Marinado (100%):", "campo_puntos": "Marinado (20 Puntos):"}]}
        _, _, areas = extractor.extraer_submission(
            _fx({"T": 90, "Marinado (100%):": 100, "Marinado (20 Puntos):": 20}), spec)
        assert areas[0] == {"area": "Marinado", "pct": 100.0, "puntos": 20.0, "puntos_max": 20.0}

    def test_pct_area_tambien_se_recorta(self):
        spec = {"score_total": "T", "areas": [
            {"area": "X", "campo_pct": "X (100%):", "campo_puntos": None}]}
        _, _, areas = extractor.extraer_submission(_fx({"T": 90, "X (100%):": 106}), spec)
        assert areas[0]["pct"] == 100.0


class TestP3Mantenimiento:
    def test_total_es_promedio_de_areas(self):
        # "Calificación General" viene 0/None; total = promedio de "AREA X" no nulos
        f = _fx({"AREA Cocina": 100, "AREA Jardinería": 80, "AREA Juegos": None,
                 "Calificación General ...": 0})
        std, raw, areas = extractor.extraer_submission(f, {}, patron="p3")
        assert std == 90.0                      # (100+80)/2, ignora el None
        assert len(areas) == 2

    def test_p3_sin_area_cae_a_metodo_normal(self):
        # mtto trimestral/semestral: sin "AREA X" -> usa score_total del spec
        spec = {"score_total": "Calif General Trim", "areas": []}
        std, _, _ = extractor.extraer_submission(_fx({"Calif General Trim": 100}), spec, patron="p3")
        assert std == 100.0
