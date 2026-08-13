"""Tests de auth (hash) y scoping (filtro SQL) — lógica pura, sin BD."""
from etl_plog.api import auth, scoping


class TestPassword:
    def test_hash_verifica(self):
        h = auth.hash_password("secreto123")
        assert auth.verifica_password("secreto123", h)

    def test_password_incorrecto(self):
        h = auth.hash_password("secreto123")
        assert not auth.verifica_password("otro", h)

    def test_hash_no_es_texto_plano(self):
        assert auth.hash_password("abc") != "abc"

    def test_verifica_hash_invalido_no_revienta(self):
        assert auth.verifica_password("x", "no-es-un-hash") is False


class TestScopeClausula:
    def test_sin_scope_no_ve_nada(self):
        w, p = scoping.clausula_scope([])
        assert w == "FALSE" and p == []

    def test_zona_null_ve_todo(self):
        w, p = scoping.clausula_scope([{"zona": None, "location_ids": None}])
        assert w == "TRUE" and p == []

    def test_una_zona_completa(self):
        w, p = scoping.clausula_scope([{"zona": "laguna", "location_ids": None}], "c")
        assert "c.zona = %s" in w and p == ["laguna"]

    def test_zona_con_sucursales_especificas(self):
        w, p = scoping.clausula_scope([{"zona": "laguna", "location_ids": [1, 2]}], "c")
        assert "location_id = ANY(%s)" in w and p == ["laguna", [1, 2]]

    def test_multiples_zonas_se_unen_con_or(self):
        w, p = scoping.clausula_scope([
            {"zona": "laguna", "location_ids": None},
            {"zona": "queretaro", "location_ids": None}])
        assert w.count("zona = %s") == 2 and " OR " in w and p == ["laguna", "queretaro"]


class TestZonasVisibles:
    def test_todas_es_none(self):
        assert scoping.zonas_visibles([{"zona": None, "location_ids": None}]) is None

    def test_conjunto_de_zonas(self):
        assert scoping.zonas_visibles([
            {"zona": "laguna"}, {"zona": "queretaro"}]) == {"laguna", "queretaro"}
