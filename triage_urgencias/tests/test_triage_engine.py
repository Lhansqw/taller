"""
test_triage_engine.py
Pruebas unitarias para el motor de triage.

Ejecutar con:  pytest tests/ -v
"""

import pytest
from backend.models import Paciente, SignosVitales
from backend.triage_engine import (
    calcular_triage,
    score_fc, score_fr, score_spo2, score_temp, score_tas, score_glasgow,
    criterios_inmediatos, ordenar_cola
)


# ─────────────────────────────────────────────
# FIXTURES — PACIENTES DE REFERENCIA
# ─────────────────────────────────────────────

def paciente_critico():
    """Paciente P1: IAM con shock."""
    return Paciente(
        nombre="Paciente Crítico", edad=60, sexo="M",
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=145, frecuencia_respiratoria=30,
            tension_arterial_sistolica=75, temperatura=36.0,
            saturacion_oxigeno=87, glasgow=12, dolor_eva=9
        ),
        sintomas=["dolor_toracico", "disnea"]
    )

def paciente_urgente():
    """Paciente P2: Dolor abdominal agudo."""
    return Paciente(
        nombre="Paciente Urgente", edad=35, sexo="F",
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=108, frecuencia_respiratoria=22,
            tension_arterial_sistolica=108, temperatura=38.9,
            saturacion_oxigeno=95, glasgow=15, dolor_eva=7
        ),
        sintomas=["dolor_abdominal", "fiebre"]
    )

def paciente_leve():
    """Paciente P4: Fractura distal sin compromiso sistémico."""
    return Paciente(
        nombre="Paciente Leve", edad=28, sexo="M",
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=78, frecuencia_respiratoria=16,
            tension_arterial_sistolica=122, temperatura=36.7,
            saturacion_oxigeno=99, glasgow=15, dolor_eva=3
        ),
        sintomas=["fractura_posible"]
    )

def paciente_pediatrico():
    """Paciente pediátrico con fiebre alta."""
    return Paciente(
        nombre="Niño Fiebre", edad=3, sexo="M",
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=130, frecuencia_respiratoria=30,
            tension_arterial_sistolica=90, temperatura=39.8,
            saturacion_oxigeno=93, glasgow=14, dolor_eva=6
        ),
        sintomas=["fiebre", "disnea"]
    )


# ─────────────────────────────────────────────
# TESTS: SCORES NEWS2 INDIVIDUALES
# ─────────────────────────────────────────────

class TestScoresNEWS2:

    def test_fc_normal(self):
        assert score_fc(75) == 0

    def test_fc_taquicardia_leve(self):
        assert score_fc(105) == 1

    def test_fc_taquicardia_severa(self):
        assert score_fc(135) == 3

    def test_fc_bradicardia_severa(self):
        assert score_fc(28) == 3

    def test_fr_normal(self):
        assert score_fr(16) == 0

    def test_fr_alta(self):
        assert score_fr(26) == 3

    def test_spo2_normal(self):
        assert score_spo2(98) == 0

    def test_spo2_hipoxemia_grave(self):
        assert score_spo2(88) == 3

    def test_temp_normal(self):
        assert score_temp(36.8) == 0

    def test_temp_fiebre(self):
        assert score_temp(39.5) == 2

    def test_temp_hipotermia(self):
        assert score_temp(34.5) == 3

    def test_tas_normal(self):
        assert score_tas(120) == 0

    def test_tas_shock(self):
        assert score_tas(85) == 3

    def test_gcs_normal(self):
        assert score_glasgow(15) == 0

    def test_gcs_severo(self):
        assert score_glasgow(7) == 3


# ─────────────────────────────────────────────
# TESTS: CRITERIOS INMEDIATOS
# ─────────────────────────────────────────────

class TestCriteriosInmediatos:

    def test_glasgow_bajo_activa_p1(self):
        sv = SignosVitales(frecuencia_cardiaca=80, frecuencia_respiratoria=16,
                           tension_arterial_sistolica=110, temperatura=36.5,
                           saturacion_oxigeno=97, glasgow=7, dolor_eva=0)
        criterios = criterios_inmediatos(sv, set(), 40)
        assert len(criterios) > 0
        assert any("Glasgow" in c for c in criterios)

    def test_spo2_bajo_activa_p1(self):
        sv = SignosVitales(frecuencia_cardiaca=80, frecuencia_respiratoria=16,
                           tension_arterial_sistolica=110, temperatura=36.5,
                           saturacion_oxigeno=85, glasgow=15, dolor_eva=0)
        criterios = criterios_inmediatos(sv, set(), 40)
        assert any("SpO2" in c for c in criterios)

    def test_sintoma_critico_activa_p1(self):
        sv = SignosVitales(frecuencia_cardiaca=80, frecuencia_respiratoria=16,
                           tension_arterial_sistolica=120, temperatura=36.8,
                           saturacion_oxigeno=98, glasgow=15, dolor_eva=0)
        criterios = criterios_inmediatos(sv, {"sincope"}, 40)
        assert len(criterios) > 0

    def test_paciente_estable_sin_criterios(self):
        sv = SignosVitales(frecuencia_cardiaca=75, frecuencia_respiratoria=16,
                           tension_arterial_sistolica=120, temperatura=36.8,
                           saturacion_oxigeno=99, glasgow=15, dolor_eva=2)
        criterios = criterios_inmediatos(sv, set(), 35)
        assert len(criterios) == 0


# ─────────────────────────────────────────────
# TESTS: CALCULAR TRIAGE COMPLETO
# ─────────────────────────────────────────────

class TestCalcularTriage:

    def test_paciente_critico_es_p1(self):
        resultado = calcular_triage(paciente_critico())
        assert resultado.prioridad == 1

    def test_paciente_urgente_es_p2_o_mejor(self):
        resultado = calcular_triage(paciente_urgente())
        assert resultado.prioridad <= 2

    def test_paciente_leve_es_p3_o_peor(self):
        resultado = calcular_triage(paciente_leve())
        assert resultado.prioridad >= 3

    def test_paciente_pediatrico_prioridad_alta(self):
        resultado = calcular_triage(paciente_pediatrico())
        assert resultado.prioridad <= 2

    def test_resultado_tiene_razones(self):
        resultado = calcular_triage(paciente_critico())
        assert len(resultado.razones) > 0

    def test_resultado_tiene_recomendaciones(self):
        resultado = calcular_triage(paciente_urgente())
        assert len(resultado.recomendaciones) > 0

    def test_score_es_numerico_positivo(self):
        resultado = calcular_triage(paciente_urgente())
        assert resultado.score >= 0

    def test_prioridad_rango_valido(self):
        for p in [paciente_critico(), paciente_urgente(), paciente_leve()]:
            r = calcular_triage(p)
            assert 1 <= r.prioridad <= 5

    def test_gcs_bajo_fuerza_p1(self):
        """Glasgow ≤8 debe forzar P1 sin importar otros signos."""
        paciente = Paciente(
            nombre="Test GCS", edad=50, sexo="M",
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=80, frecuencia_respiratoria=18,
                tension_arterial_sistolica=115, temperatura=37.0,
                saturacion_oxigeno=96, glasgow=7, dolor_eva=0
            ),
            sintomas=[]
        )
        resultado = calcular_triage(paciente)
        assert resultado.prioridad == 1

    def test_anciano_aumenta_prioridad(self):
        """Paciente de 82 años debe obtener prioridad más alta que uno de 35 con mismos vitales."""
        sv_base = SignosVitales(frecuencia_cardiaca=92, frecuencia_respiratoria=20,
                                tension_arterial_sistolica=112, temperatura=38.2,
                                saturacion_oxigeno=95, glasgow=15, dolor_eva=4)
        joven = Paciente(nombre="Joven", edad=35, sexo="M", signos_vitales=sv_base, sintomas=[])
        anciano = Paciente(nombre="Anciano", edad=82, sexo="M", signos_vitales=sv_base, sintomas=[])

        r_joven = calcular_triage(joven)
        r_anciano = calcular_triage(anciano)
        assert r_anciano.prioridad <= r_joven.prioridad  # anciano igual o más urgente


# ─────────────────────────────────────────────
# TESTS: ORDENAMIENTO DE COLA
# ─────────────────────────────────────────────

class TestOrdenarCola:

    def test_p1_siempre_primero(self):
        p1 = paciente_critico()
        p1.prioridad = 1; p1.score_news2 = 14; p1.minutos_espera = 2

        p4 = paciente_leve()
        p4.prioridad = 4; p4.score_news2 = 2; p4.minutos_espera = 60

        cola = ordenar_cola([p4, p1])
        assert cola[0].prioridad == 1

    def test_mismo_prioridad_mayor_espera_primero(self):
        from copy import deepcopy
        p_a = paciente_urgente(); p_a.prioridad = 2; p_a.score_news2 = 8; p_a.minutos_espera = 14
        p_b = deepcopy(p_a);     p_b.nombre = "B"; p_b.minutos_espera = 5

        cola = ordenar_cola([p_b, p_a])
        # p_a lleva más tiempo → mayor urgencia relativa
        assert cola[0].minutos_espera >= cola[1].minutos_espera