"""
triage_engine.py
Motor principal de cálculo de triage.

Implementa:
  - Algoritmo NEWS2 (National Early Warning Score 2) de la NHS
  - Criterios de activación inmediata (Manchester / ESI)
  - Factores de riesgo demográficos (edad, comorbilidades)
  - Clasificación final por prioridad 1-5

Referencia: Royal College of Physicians. National Early Warning Score (NEWS) 2.
            London: RCP, 2017.
"""

from typing import Set, List, Tuple
from backend.models import (
    Paciente, SignosVitales, ResultadoTriage,
    PRIORIDAD_INFO, CATALOGO_SINTOMAS
)


# ─────────────────────────────────────────────
# TABLAS NEWS2 (puntuación por parámetro)
# ─────────────────────────────────────────────

def score_fc(fc: int) -> int:
    """Frecuencia cardíaca → puntos NEWS2."""
    if fc <= 40:          return 3
    elif fc <= 50:        return 1
    elif fc <= 90:        return 0
    elif fc <= 110:       return 1
    elif fc <= 130:       return 2
    else:                 return 3

def score_fr(fr: int) -> int:
    """Frecuencia respiratoria → puntos NEWS2."""
    if fr <= 8:           return 3
    elif fr <= 11:        return 1
    elif fr <= 20:        return 0
    elif fr <= 24:        return 2
    else:                 return 3

def score_spo2(spo2: int) -> int:
    """Saturación de oxígeno → puntos NEWS2."""
    if spo2 <= 91:        return 3
    elif spo2 <= 93:      return 2
    elif spo2 <= 95:      return 1
    else:                 return 0

def score_temp(t: float) -> int:
    """Temperatura → puntos NEWS2."""
    if t <= 35.0:         return 3
    elif t <= 36.0:       return 1
    elif t <= 38.0:       return 0
    elif t <= 39.0:       return 1
    else:                 return 2

def score_tas(tas: int) -> int:
    """Tensión arterial sistólica → puntos NEWS2."""
    if tas <= 90:         return 3
    elif tas <= 100:      return 2
    elif tas <= 110:      return 1
    elif tas <= 219:      return 0
    else:                 return 3

def score_glasgow(gcs: int) -> int:
    """Glasgow → puntos NEWS2 (consciencia)."""
    if gcs >= 15:         return 0
    elif gcs >= 14:       return 1
    elif gcs >= 12:       return 2
    else:                 return 3

def score_dolor(eva: int) -> int:
    """Dolor EVA → puntos adicionales (extensión propia)."""
    if eva >= 8:          return 2
    elif eva >= 5:        return 1
    else:                 return 0


# ─────────────────────────────────────────────
# CRITERIOS DE ACTIVACIÓN INMEDIATA (P1 directo)
# ─────────────────────────────────────────────

SINTOMAS_CRITICOS = {
    "dolor_toracico", "sincope", "hemorragia",
    "deficit_neuro", "quemaduras", "reaccion_alergica"
}

def criterios_inmediatos(sv: SignosVitales, sintomas: Set[str], edad: int) -> List[str]:
    """
    Evalúa criterios que eleva al paciente directamente a P1.
    Retorna lista de razones críticas encontradas.
    """
    razones = []

    # Signos vitales con riesgo vital
    if sv.glasgow <= 8:
        razones.append(f"🚨 Glasgow ≤8 ({sv.glasgow}): Compromiso severo de consciencia")
    if sv.saturacion_oxigeno < 90:
        razones.append(f"🚨 SpO2 <90% ({sv.saturacion_oxigeno}%): Hipoxemia grave")
    if sv.tension_arterial_sistolica < 70:
        razones.append(f"🚨 TAS <70 mmHg ({sv.tension_arterial_sistolica}): Shock descompensado")
    if sv.frecuencia_cardiaca > 150 or sv.frecuencia_cardiaca < 30:
        razones.append(f"🚨 FC {sv.frecuencia_cardiaca} lpm: Inestabilidad hemodinámica crítica")
    if sv.frecuencia_respiratoria > 35 or sv.frecuencia_respiratoria < 6:
        razones.append(f"🚨 FR {sv.frecuencia_respiratoria} rpm: Insuficiencia respiratoria")
    if sv.temperatura > 41.0:
        razones.append(f"🚨 Temperatura {sv.temperatura}°C: Hipertermia extrema")
    if sv.temperatura < 35.0:
        razones.append(f"🚨 Temperatura {sv.temperatura}°C: Hipotermia grave")

    # Síntomas críticos
    criticos_presentes = SINTOMAS_CRITICOS.intersection(sintomas)
    if criticos_presentes:
        nombres = [s.replace("_", " ").capitalize() for s in criticos_presentes]
        razones.append(f"🚨 Síntoma(s) crítico(s): {', '.join(nombres)}")

    return razones


# ─────────────────────────────────────────────
# FACTORES DE RIESGO DEMOGRÁFICOS
# ─────────────────────────────────────────────

def factores_demograficos(edad: int, sintomas: Set[str]) -> Tuple[int, List[str]]:
    """
    Calcula puntos adicionales y razones por factores de riesgo.
    Retorna (puntos_extra, [razones])
    """
    puntos = 0
    razones = []

    if edad >= 80:
        puntos += 2
        razones.append("📌 Paciente geriátrico (≥80 años): mayor vulnerabilidad fisiológica")
    elif edad >= 65:
        puntos += 1
        razones.append("📌 Paciente mayor (≥65 años): riesgo elevado de deterioro rápido")
    elif edad <= 5:
        puntos += 2
        razones.append("📌 Paciente pediátrico (≤5 años): reserva fisiológica limitada")
    elif edad <= 14:
        puntos += 1
        razones.append("📌 Paciente pediátrico (≤14 años)")

    return puntos, razones


# ─────────────────────────────────────────────
# PUNTOS POR SÍNTOMAS NO CRÍTICOS
# ─────────────────────────────────────────────

def puntos_sintomas(sintomas: Set[str]) -> float:
    """Suma el peso de síntomas no críticos presentes."""
    total = 0.0
    catalogo = {s.codigo: s for s in CATALOGO_SINTOMAS}
    for cod in sintomas:
        sym = catalogo.get(cod)
        if sym and not sym.es_critico:
            total += sym.peso * 0.5  # Factor reducido para no-críticos
    return total


# ─────────────────────────────────────────────
# PRIORIDAD DESDE SCORE NEWS2
# ─────────────────────────────────────────────

def prioridad_por_score(score: float) -> int:
    """
    Mapea el score NEWS2 total a una prioridad de triage.
    Umbrales basados en evidencia clínica (RCP 2017).
    """
    if score >= 12:   return 1
    elif score >= 7:  return 2
    elif score >= 4:  return 3
    elif score >= 1:  return 4
    else:             return 4


# ─────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────

def calcular_triage(paciente: Paciente) -> ResultadoTriage:
    """
    Algoritmo principal de triage.

    Flujo:
    1. Evaluar criterios inmediatos (P1 automático si hay riesgo vital)
    2. Calcular score NEWS2 fisiológico
    3. Sumar factores demográficos
    4. Sumar puntos por síntomas
    5. Determinar prioridad final (la más urgente entre criterios y score)
    6. Generar razones y recomendaciones
    """
    sv = paciente.signos_vitales
    sintomas = set(paciente.sintomas)
    razones: List[str] = []

    # PASO 1: Criterios inmediatos
    criterios = criterios_inmediatos(sv, sintomas, paciente.edad)
    forzar_p1 = len(criterios) > 0
    razones.extend(criterios)

    # PASO 2: Score NEWS2 base
    score_base = (
        score_fc(sv.frecuencia_cardiaca) +
        score_fr(sv.frecuencia_respiratoria) +
        score_spo2(sv.saturacion_oxigeno) +
        score_temp(sv.temperatura) +
        score_tas(sv.tension_arterial_sistolica) +
        score_glasgow(sv.glasgow) +
        score_dolor(sv.dolor_eva)
    )

    # PASO 3: Factores demográficos
    puntos_extra, razones_demo = factores_demograficos(paciente.edad, sintomas)
    razones.extend(razones_demo)

    # PASO 4: Síntomas no críticos
    puntos_sym = puntos_sintomas(sintomas)

    # Score total
    score_total = score_base + puntos_extra + puntos_sym

    # PASO 5: Prioridad final
    prioridad_score = prioridad_por_score(score_total)
    prioridad_final = 1 if forzar_p1 else prioridad_score

    # Añadir información del score
    if score_total > 0:
        razones.append(f"📊 Score NEWS2: {score_total:.1f} puntos (FC:{score_fc(sv.frecuencia_cardiaca)} FR:{score_fr(sv.frecuencia_respiratoria)} SpO2:{score_spo2(sv.saturacion_oxigeno)} T°:{score_temp(sv.temperatura)} TA:{score_tas(sv.tension_arterial_sistolica)} GCS:{score_glasgow(sv.glasgow)})")

    if len(razones) == 0:
        razones.append("✅ Paciente estable — Sin criterios de urgencia mayor detectados")

    # PASO 6: Ensamblar resultado
    info = PRIORIDAD_INFO[prioridad_final]

    return ResultadoTriage(
        prioridad=prioridad_final,
        label=info["label"],
        color_hex=info["color_hex"],
        tiempo_max_espera_min=info["tiempo_max"],
        score=round(score_total, 1),
        razones=razones,
        recomendaciones=info["recomendacion"],
        alertas_vitales=sv.alertas()
    )


# ─────────────────────────────────────────────
# ORDENAMIENTO DE COLA
# ─────────────────────────────────────────────

def ordenar_cola(pacientes: List[Paciente]) -> List[Paciente]:
    """
    Ordena la cola de atención por:
    1. Prioridad (P1 primero)
    2. Tiempo de espera relativo al máximo permitido
    3. Score NEWS2 descendente
    """
    def clave_orden(p: Paciente):
        info = PRIORIDAD_INFO.get(p.prioridad or 4, {})
        tiempo_max = info.get("tiempo_max") or 999
        urgencia_tiempo = p.minutos_espera / tiempo_max if tiempo_max else 0
        return (p.prioridad or 4, -urgencia_tiempo, -(p.score_news2 or 0))

    return sorted(pacientes, key=clave_orden)


# ─────────────────────────────────────────────
# ALERTA DE SOBRECUPO
# ─────────────────────────────────────────────

def verificar_tiempos_espera(pacientes: List[Paciente]) -> List[dict]:
    """
    Devuelve alertas de pacientes que han superado su tiempo máximo de espera.
    """
    alertas = []
    for p in pacientes:
        if p.estado != "espera":
            continue
        info = PRIORIDAD_INFO.get(p.prioridad or 4, {})
        tiempo_max = info.get("tiempo_max")
        if tiempo_max and p.minutos_espera > tiempo_max:
            alertas.append({
                "paciente_id": p.id,
                "nombre": p.nombre,
                "prioridad": p.prioridad,
                "minutos_espera": p.minutos_espera,
                "tiempo_max": tiempo_max,
                "exceso_min": round(p.minutos_espera - tiempo_max, 1)
            })
    return alertas