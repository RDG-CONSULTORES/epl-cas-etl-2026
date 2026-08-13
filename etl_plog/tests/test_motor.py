"""Tests del motor de cumplimiento (lógica pura, sin BD).

Correr:  .venv-plog/bin/python -m pytest etl_plog/tests/test_motor.py -q
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from etl_plog.cumplimiento import motor

MTY = ZoneInfo("America/Monterrey")


def _dt(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=MTY)


# ── _estado: los 4 estados y los bordes ──────────────────────────────────
class TestEstado:
    def test_on_time(self):
        # entregado antes del límite 15:00
        assert motor._estado(date(2026, 7, 1), time(15), False, 0,
                             _dt(2026, 7, 1, 14), _dt(2026, 7, 2, 9)) == "on_time"

    def test_late(self):
        # entregado después del límite pero registrado
        assert motor._estado(date(2026, 7, 1), time(15), False, 0,
                             _dt(2026, 7, 1, 16), _dt(2026, 7, 2, 9)) == "late"

    def test_missed(self):
        # sin entrega y ya venció límite+gracia
        assert motor._estado(date(2026, 7, 1), time(15), False, 0,
                             None, _dt(2026, 7, 5, 9)) == "missed"

    def test_pending_dentro_de_ventana(self):
        # sin entrega pero AÚN no vence (mismo día antes del límite)
        assert motor._estado(date(2026, 7, 1), time(15), False, 0,
                             None, _dt(2026, 7, 1, 10)) == "pending"

    def test_pending_respeta_gracia(self):
        # sin entrega, venció límite pero dentro de días de gracia -> pending, no missed
        assert motor._estado(date(2026, 7, 1), None, False, 2,
                             None, _dt(2026, 7, 2, 10)) == "pending"

    def test_missed_tras_gracia(self):
        assert motor._estado(date(2026, 7, 1), None, False, 2,
                             None, _dt(2026, 7, 5, 10)) == "missed"

    def test_dia_siguiente(self):
        # cierre con límite 01:00 del día siguiente: entrega a las 00:30 del día+1 = on_time
        assert motor._estado(date(2026, 7, 1), time(1), True, 0,
                             _dt(2026, 7, 2, 0, 30), _dt(2026, 7, 3, 9)) == "on_time"


# ── _limites: deadline y cierre ──────────────────────────────────────────
class TestLimites:
    def test_limite_simple(self):
        lim, gr = motor._limites(date(2026, 7, 1), time(15), False, 0)
        assert lim == _dt(2026, 7, 1, 15) and gr == lim

    def test_gracia_suma_dias(self):
        lim, gr = motor._limites(date(2026, 7, 1), time(15), False, 2)
        assert (gr - lim).days == 2

    def test_sin_hora_usa_fin_de_dia(self):
        lim, _ = motor._limites(date(2026, 7, 1), None, False, 0)
        assert lim.hour == 23 and lim.minute == 59


# ── _ventanas: generación por frecuencia ────────────────────────────────
class TestVentanas:
    def test_diario_una_por_dia(self):
        v = list(motor._ventanas("diario", date(2026, 7, 1), date(2026, 7, 7), {}))
        assert len(v) == 7
        assert all(ini == fin for ini, fin, _ in v)

    def test_semanal_lunes_a_domingo(self):
        v = list(motor._ventanas("semanal", date(2026, 7, 6), date(2026, 7, 12), {}))
        # 6-jul-2026 es lunes; una ventana lun-dom
        assert len(v) == 1
        ini, fin, _ = v[0]
        assert ini.weekday() == 0 and (fin - ini).days == 6

    def test_mensual_una_por_mes(self):
        v = list(motor._ventanas("mensual", date(2026, 7, 1), date(2026, 8, 31), {}))
        assert len(v) == 2  # julio y agosto

    def test_por_visita_no_genera(self):
        assert list(motor._ventanas("por_visita", date(2026, 7, 1), date(2026, 7, 31), {})) == []


# ── Alistamiento: mapeo día+serie ────────────────────────────────────────
class TestAlistamiento:
    def test_ft_dia_serie_lunes(self):
        assert motor.FT_DIA_SERIE[954598] == ("lun", "A")   # A1
        assert motor.FT_DIA_SERIE[1040507] == ("lun", "L")  # L1

    def test_ft_dia_serie_domingo(self):
        assert motor.FT_DIA_SERIE[1010538] == ("dom", "A")  # A7
        assert motor.FT_DIA_SERIE[1038658] == ("dom", "L")  # L7

    def test_ambas_series_son_alistamiento(self):
        assert motor.ALISTAMIENTO_FAMILIAS == {"alistamiento_a", "alistamiento_l"}

    def test_cobertura_14_templates(self):
        # 7 días × 2 series = 14 form templates mapeados
        assert len(motor.FT_DIA_SERIE) == 14
