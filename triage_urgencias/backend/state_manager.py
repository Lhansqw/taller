"""
state_manager.py
Gestor de estado de la sala de urgencias.

Maneja:
  - Cola de pacientes en memoria (simulando una BD)
  - Recursos hospitalarios en tiempo real
  - Historial de acciones (auditoría)
  - Estadísticas del turno

En producción real se reemplazaría con una BD (PostgreSQL + SQLAlchemy).
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict
from backend.models import Paciente, RecursosHospital, Recurso
from backend.triage_engine import ordenar_cola, verificar_tiempos_espera


class GestorUrgencias:
    """
    Singleton que mantiene el estado completo de la sala de urgencias.
    En Streamlit se almacena en st.session_state para persistencia entre rerenders.
    """

    def __init__(self):
        self.pacientes: List[Paciente] = []
        self.recursos: RecursosHospital = RecursosHospital()
        self.historial: List[Dict] = []
        self.inicio_turno: datetime = datetime.now()

    # ─────────────────────────────────────────
    # GESTIÓN DE PACIENTES
    # ─────────────────────────────────────────

    def registrar_paciente(self, paciente: Paciente) -> Paciente:
        """
        Registra un nuevo paciente en la cola.
        Asigna ID único y hora de ingreso.
        """
        paciente.id = str(uuid.uuid4())[:8].upper()
        paciente.hora_ingreso = datetime.now()
        paciente.estado = "espera"
        paciente.minutos_espera = 0.0
        self.pacientes.append(paciente)
        self._registrar_accion("INGRESO", paciente.id, f"Paciente {paciente.nombre} ingresado con prioridad P{paciente.prioridad}")
        return paciente

    def obtener_cola_ordenada(self) -> List[Paciente]:
        """Retorna la cola ordenada por prioridad y urgencia de espera."""
        activos = [p for p in self.pacientes if p.estado not in ("alta", "fallecido")]
        return ordenar_cola(activos)

    def cambiar_estado(self, paciente_id: str, nuevo_estado: str) -> Optional[Paciente]:
        """Cambia el estado de un paciente y actualiza recursos si aplica."""
        paciente = self._buscar(paciente_id)
        if not paciente:
            return None

        estado_anterior = paciente.estado
        paciente.estado = nuevo_estado

        # Ajuste de recursos según transición
        self._ajustar_recursos_por_estado(estado_anterior, nuevo_estado, paciente)
        self._registrar_accion("ESTADO", paciente_id,
                               f"{paciente.nombre}: {estado_anterior} → {nuevo_estado}")
        return paciente

    def actualizar_notas(self, paciente_id: str, notas: str) -> bool:
        paciente = self._buscar(paciente_id)
        if not paciente:
            return False
        paciente.notas_clinicas = notas
        return True

    def eliminar_paciente(self, paciente_id: str) -> bool:
        antes = len(self.pacientes)
        self.pacientes = [p for p in self.pacientes if p.id != paciente_id]
        return len(self.pacientes) < antes

    def actualizar_tiempos_espera(self, incremento_min: float = 0.5):
        """Incrementa el tiempo de espera de pacientes en cola. Llamar cada 30s."""
        for p in self.pacientes:
            if p.estado == "espera":
                p.minutos_espera += incremento_min

    # ─────────────────────────────────────────
    # ALERTAS
    # ─────────────────────────────────────────

    def obtener_alertas(self) -> List[dict]:
        """Pacientes que han superado su tiempo máximo de espera."""
        activos = [p for p in self.pacientes if p.estado == "espera"]
        return verificar_tiempos_espera(activos)

    # ─────────────────────────────────────────
    # ESTADÍSTICAS DEL TURNO
    # ─────────────────────────────────────────

    def estadisticas(self) -> Dict:
        """Resumen estadístico del turno actual."""
        total = len(self.pacientes)
        por_prioridad = {}
        for p in [1, 2, 3, 4, 5]:
            por_prioridad[f"P{p}"] = len([x for x in self.pacientes if x.prioridad == p])

        en_espera = len([x for x in self.pacientes if x.estado == "espera"])
        en_atencion = len([x for x in self.pacientes if x.estado == "atencion"])
        altas = len([x for x in self.pacientes if x.estado == "alta"])

        scores = [x.score_news2 for x in self.pacientes if x.score_news2 is not None]
        score_promedio = round(sum(scores) / len(scores), 1) if scores else 0

        tiempo_espera_prom = 0.0
        tiempos = [x.minutos_espera for x in self.pacientes if x.estado == "espera"]
        if tiempos:
            tiempo_espera_prom = round(sum(tiempos) / len(tiempos), 1)

        return {
            "total_pacientes": total,
            "por_prioridad": por_prioridad,
            "en_espera": en_espera,
            "en_atencion": en_atencion,
            "altas_turno": altas,
            "score_promedio": score_promedio,
            "tiempo_espera_promedio_min": tiempo_espera_prom,
            "alertas_activas": len(self.obtener_alertas()),
            "duracion_turno_min": round((datetime.now() - self.inicio_turno).seconds / 60, 1)
        }

    # ─────────────────────────────────────────
    # RECURSOS
    # ─────────────────────────────────────────

    def _ajustar_recursos_por_estado(self, anterior: str, nuevo: str, p: Paciente):
        """Actualiza disponibilidad de recursos según cambio de estado."""
        if nuevo == "atencion":
            # Asignar cama y médico
            if p.prioridad <= 2:
                self.recursos.camas_uci.disponibles = max(0, self.recursos.camas_uci.disponibles - 1)
            else:
                self.recursos.camas_obs.disponibles = max(0, self.recursos.camas_obs.disponibles - 1)
            self.recursos.medicos.disponibles = max(0, self.recursos.medicos.disponibles - 1)

        elif nuevo == "traslado":
            self.recursos.quirofano.disponibles = max(0, self.recursos.quirofano.disponibles - 1)

        elif nuevo in ("alta", "fallecido"):
            # Liberar recursos
            if anterior == "atencion":
                if p.prioridad <= 2:
                    self.recursos.camas_uci.disponibles = min(
                        self.recursos.camas_uci.total,
                        self.recursos.camas_uci.disponibles + 1
                    )
                else:
                    self.recursos.camas_obs.disponibles = min(
                        self.recursos.camas_obs.total,
                        self.recursos.camas_obs.disponibles + 1
                    )
                self.recursos.medicos.disponibles = min(
                    self.recursos.medicos.total,
                    self.recursos.medicos.disponibles + 1
                )
            elif anterior == "traslado":
                self.recursos.quirofano.disponibles = min(
                    self.recursos.quirofano.total,
                    self.recursos.quirofano.disponibles + 1
                )

    # ─────────────────────────────────────────
    # AUDITORÍA
    # ─────────────────────────────────────────

    def _registrar_accion(self, tipo: str, paciente_id: str, descripcion: str):
        self.historial.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "tipo": tipo,
            "paciente_id": paciente_id,
            "descripcion": descripcion
        })

    def _buscar(self, paciente_id: str) -> Optional[Paciente]:
        return next((p for p in self.pacientes if p.id == paciente_id), None)

    # ─────────────────────────────────────────
    # DATOS DEMO
    # ─────────────────────────────────────────

    def cargar_demo(self):
        """Carga pacientes de ejemplo para demostración del taller."""
        from backend.models import SignosVitales
        from backend.triage_engine import calcular_triage

        demos = [
            {
                "nombre": "Carlos Muñoz", "edad": 58, "sexo": "M",
                "sv": SignosVitales(frecuencia_cardiaca=142, frecuencia_respiratoria=28,
                                   tension_arterial_sistolica=80, temperatura=36.2,
                                   saturacion_oxigeno=88, glasgow=13, dolor_eva=9),
                "sintomas": ["dolor_toracico", "disnea"],
                "antecedentes": "IAM anterior. Diaforesis profusa.",
                "minutos_espera": 8.0
            },
            {
                "nombre": "Ana Rodríguez", "edad": 34, "sexo": "F",
                "sv": SignosVitales(frecuencia_cardiaca=105, frecuencia_respiratoria=22,
                                   tension_arterial_sistolica=110, temperatura=38.8,
                                   saturacion_oxigeno=95, glasgow=15, dolor_eva=6),
                "sintomas": ["dolor_abdominal", "vomito_nausea"],
                "antecedentes": "Dolor en FID hace 6h. Posible apendicitis.",
                "minutos_espera": 9.0
            },
            {
                "nombre": "Pedro Gómez", "edad": 72, "sexo": "M",
                "sv": SignosVitales(frecuencia_cardiaca=88, frecuencia_respiratoria=18,
                                   tension_arterial_sistolica=130, temperatura=37.1,
                                   saturacion_oxigeno=97, glasgow=15, dolor_eva=3),
                "sintomas": ["fiebre"],
                "antecedentes": "ITU recurrente. HTA.",
                "minutos_espera": 5.0
            },
            {
                "nombre": "Lucía Torres", "edad": 8, "sexo": "F",
                "sv": SignosVitales(frecuencia_cardiaca=130, frecuencia_respiratoria=30,
                                   tension_arterial_sistolica=95, temperatura=39.5,
                                   saturacion_oxigeno=92, glasgow=14, dolor_eva=7),
                "sintomas": ["disnea", "fiebre"],
                "antecedentes": "Crisis asmática. Sin respuesta a broncodilatador domiciliario.",
                "minutos_espera": 12.0
            },
            {
                "nombre": "Roberto Lima", "edad": 45, "sexo": "M",
                "sv": SignosVitales(frecuencia_cardiaca=76, frecuencia_respiratoria=16,
                                   tension_arterial_sistolica=125, temperatura=36.8,
                                   saturacion_oxigeno=99, glasgow=15, dolor_eva=4),
                "sintomas": ["fractura_posible"],
                "antecedentes": "Caída de bicicleta. Dolor en muñeca derecha.",
                "minutos_espera": 3.0
            },
        ]

        for d in demos:
            p = Paciente(
                nombre=d["nombre"], edad=d["edad"], sexo=d["sexo"],
                signos_vitales=d["sv"],
                sintomas=d["sintomas"],
                antecedentes=d.get("antecedentes")
            )
            resultado = calcular_triage(p)
            p.prioridad = resultado.prioridad
            p.score_news2 = resultado.score
            p.razones_triage = resultado.razones
            self.registrar_paciente(p)
            # Sobreescribir tiempo de espera del demo
            self._buscar(p.id).minutos_espera = d["minutos_espera"]