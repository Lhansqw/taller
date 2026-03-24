"""
models.py
Modelos de datos del sistema de Triage usando Pydantic.
Representan las entidades principales: Paciente, SignosVitales, ResultadoTriage, Recurso.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from enum import IntEnum
from datetime import datetime


# ─────────────────────────────────────────────
# ENUMERACIONES
# ─────────────────────────────────────────────

class Prioridad(IntEnum):
    """Escala de prioridad según estándar Manchester/ESI."""
    P1_ROJO    = 1  # Inmediato  (<5 min)   — Riesgo vital
    P2_NARANJA = 2  # Urgente    (<15 min)  — Compromiso grave
    P3_AMARILLO= 3  # Menos urgente (<30 min)
    P4_VERDE   = 4  # No urgente (<120 min)
    P5_NEGRO   = 5  # Expectante — Sin posibilidad

class EstadoPaciente(str):
    ESPERA    = "espera"
    ATENCION  = "atencion"
    TRASLADO  = "traslado"
    ALTA      = "alta"
    FALLECIDO = "fallecido"

class Sexo(str):
    M = "M"
    F = "F"
    O = "O"


# ─────────────────────────────────────────────
# SIGNOS VITALES
# ─────────────────────────────────────────────

class SignosVitales(BaseModel):
    """
    Signos vitales con rangos de referencia clínica.
    Valores fuera de rango disparan alertas automáticas.
    """
    frecuencia_cardiaca: int = Field(..., ge=0, le=300, description="Latidos por minuto")
    frecuencia_respiratoria: int = Field(..., ge=0, le=60, description="Respiraciones por minuto")
    tension_arterial_sistolica: int = Field(..., ge=0, le=300, description="mmHg")
    temperatura: float = Field(..., ge=28.0, le=45.0, description="Grados Celsius")
    saturacion_oxigeno: int = Field(..., ge=0, le=100, description="SpO2 %")
    glasgow: int = Field(15, ge=3, le=15, description="Escala de Coma de Glasgow")
    dolor_eva: int = Field(0, ge=0, le=10, description="Escala Visual Analógica")

    @field_validator("frecuencia_cardiaca")
    @classmethod
    def fc_rango(cls, v: int) -> int:
        if v < 30 or v > 200:
            pass  # Se maneja en el motor de triage como criterio crítico
        return v

    def alertas(self) -> List[str]:
        """Devuelve lista de parámetros fuera de rango normal."""
        alertas = []
        if self.frecuencia_cardiaca > 120 or self.frecuencia_cardiaca < 50:
            alertas.append(f"⚠️ FC anormal: {self.frecuencia_cardiaca} lpm")
        if self.frecuencia_respiratoria > 25 or self.frecuencia_respiratoria < 10:
            alertas.append(f"⚠️ FR anormal: {self.frecuencia_respiratoria} rpm")
        if self.tension_arterial_sistolica < 100 or self.tension_arterial_sistolica > 180:
            alertas.append(f"⚠️ TAS anormal: {self.tension_arterial_sistolica} mmHg")
        if self.temperatura > 38.5 or self.temperatura < 36.0:
            alertas.append(f"⚠️ Temperatura: {self.temperatura}°C")
        if self.saturacion_oxigeno < 95:
            alertas.append(f"⚠️ SpO2 baja: {self.saturacion_oxigeno}%")
        if self.glasgow < 15:
            alertas.append(f"⚠️ Glasgow reducido: {self.glasgow}/15")
        return alertas


# ─────────────────────────────────────────────
# PACIENTE
# ─────────────────────────────────────────────

class Sintoma(BaseModel):
    codigo: str
    descripcion: str
    peso: float       # Peso clínico en el score
    es_critico: bool  # Si es True → eleva automáticamente a P1


CATALOGO_SINTOMAS: List[Sintoma] = [
    Sintoma(codigo="dolor_toracico",    descripcion="Dolor torácico",           peso=4.0, es_critico=True),
    Sintoma(codigo="disnea",            descripcion="Disnea / dificultad resp.",peso=3.0, es_critico=True),
    Sintoma(codigo="sincope",           descripcion="Síncope / pérdida de consciencia", peso=4.0, es_critico=True),
    Sintoma(codigo="hemorragia",        descripcion="Hemorragia activa",        peso=4.0, es_critico=True),
    Sintoma(codigo="deficit_neuro",     descripcion="Déficit neurológico",      peso=4.0, es_critico=True),
    Sintoma(codigo="quemaduras",        descripcion="Quemaduras",               peso=3.0, es_critico=True),
    Sintoma(codigo="reaccion_alergica", descripcion="Reacción alérgica grave",  peso=3.0, es_critico=True),
    Sintoma(codigo="trauma",            descripcion="Trauma/politraumatismo",   peso=3.0, es_critico=False),
    Sintoma(codigo="fiebre",            descripcion="Fiebre alta",              peso=2.0, es_critico=False),
    Sintoma(codigo="dolor_abdominal",   descripcion="Dolor abdominal",          peso=2.0, es_critico=False),
    Sintoma(codigo="vomito_nausea",     descripcion="Vómito / náusea",          peso=1.0, es_critico=False),
    Sintoma(codigo="fractura_posible",  descripcion="Fractura posible",         peso=2.0, es_critico=False),
]


class Paciente(BaseModel):
    """Entidad principal del sistema."""
    id: Optional[str] = None
    nombre: str = Field(..., min_length=2, max_length=100)
    edad: int = Field(..., ge=0, le=120)
    sexo: str = Field(default="M", pattern=r"^[MFO]$")
    signos_vitales: SignosVitales
    sintomas: List[str] = Field(default_factory=list, description="Códigos de síntomas presentes")
    antecedentes: Optional[str] = None
    hora_ingreso: Optional[datetime] = None
    prioridad: Optional[int] = None
    score_news2: Optional[float] = None
    estado: str = "espera"
    minutos_espera: float = 0.0
    razones_triage: List[str] = Field(default_factory=list)
    notas_clinicas: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# ─────────────────────────────────────────────
# RESULTADO DE TRIAGE
# ─────────────────────────────────────────────

class ResultadoTriage(BaseModel):
    prioridad: int
    label: str
    color_hex: str
    tiempo_max_espera_min: Optional[int]
    score: float
    razones: List[str]
    recomendaciones: List[str]
    alertas_vitales: List[str]


PRIORIDAD_INFO = {
    1: {
        "label": "P1 — ROJO — INMEDIATO",
        "color_hex": "#ef4444",
        "tiempo_max": 5,
        "recomendacion": ["Activar código de emergencia", "Monitoreo continuo", "Vía venosa central", "Preparar UCI"]
    },
    2: {
        "label": "P2 — NARANJA — URGENTE",
        "color_hex": "#f97316",
        "tiempo_max": 15,
        "recomendacion": ["Evaluación médica inmediata", "Monitoreo cada 5 min", "Acceso venoso periférico", "ECG si dolor torácico"]
    },
    3: {
        "label": "P3 — AMARILLO — MENOS URGENTE",
        "color_hex": "#eab308",
        "tiempo_max": 30,
        "recomendacion": ["Evaluación en 30 min", "Control de signos vitales", "Analgesia si necesario"]
    },
    4: {
        "label": "P4 — VERDE — NO URGENTE",
        "color_hex": "#22c55e",
        "tiempo_max": 120,
        "recomendacion": ["Atención en sala general", "Reval. si empeora", "Puede esperar en sala de espera"]
    },
    5: {
        "label": "P5 — NEGRO — EXPECTANTE",
        "color_hex": "#6b7280",
        "tiempo_max": None,
        "recomendacion": ["Solo cuidados paliativos", "Evitar recursos escasos", "Apoyo familiar"]
    },
}


# ─────────────────────────────────────────────
# RECURSOS HOSPITALARIOS
# ─────────────────────────────────────────────

class Recurso(BaseModel):
    nombre: str
    disponibles: int
    total: int

    @property
    def ocupacion_pct(self) -> float:
        return (self.disponibles / self.total) * 100 if self.total > 0 else 0

    @property
    def estado(self) -> str:
        pct = self.ocupacion_pct
        if pct >= 80:
            return "critico"
        elif pct >= 50:
            return "moderado"
        return "disponible"


class RecursosHospital(BaseModel):
    camas_uci: Recurso = Recurso(nombre="Camas UCI", disponibles=2, total=5)
    camas_obs: Recurso = Recurso(nombre="Camas Observación", disponibles=3, total=5)
    medicos: Recurso = Recurso(nombre="Médicos", disponibles=3, total=4)
    enfermeros: Recurso = Recurso(nombre="Enfermeros", disponibles=4, total=6)
    quirofano: Recurso = Recurso(nombre="Quirófanos", disponibles=1, total=2)
    ventiladores: Recurso = Recurso(nombre="Ventiladores", disponibles=2, total=5)