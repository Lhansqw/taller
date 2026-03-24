# 🏥 Sistema de Triage y Flujo de Sala de Urgencias

Taller académico — Backend Python + Frontend Streamlit

## 🚀 Instalación y Ejecución

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar la aplicación
streamlit run app.py

# 3. Ejecutar pruebas
pytest tests/ -v
```

## 🏗️ Arquitectura del Proyecto

```
triage_urgencias/
│
├── app.py                      # Punto de entrada Streamlit
├── requirements.txt
│
├── backend/
│   ├── __init__.py
│   ├── models.py               # Modelos Pydantic (Paciente, SignosVitales, etc.)
│   ├── triage_engine.py        # Algoritmo NEWS2 + Manchester
│   └── state_manager.py        # Gestor de estado (cola, recursos, auditoría)
│
├── frontend/
│   ├── __init__.py
│   └── components.py           # Componentes UI reutilizables de Streamlit
│
├── tests/
│   └── test_triage_engine.py   # Pruebas unitarias del motor
│
└── data/                       # (Opcional) CSVs, exportaciones de turno
```

## 🧠 Algoritmo de Triage

El motor implementa el estándar **NEWS2** (National Early Warning Score 2) de la NHS combinado
con criterios de activación inmediata del protocolo **Manchester**:

### Parámetros evaluados

| Parámetro             | Rango normal  | Puntos en riesgo |
|-----------------------|---------------|-----------------|
| Frecuencia cardíaca   | 51-90 lpm     | Hasta 3 pts     |
| Frecuencia resp.      | 12-20 rpm     | Hasta 3 pts     |
| SpO₂                  | ≥96%          | Hasta 3 pts     |
| Temperatura           | 36.1-38.0°C   | Hasta 3 pts     |
| Tensión arterial      | 111-219 mmHg  | Hasta 3 pts     |
| Glasgow               | 15            | Hasta 3 pts     |
| Dolor EVA             | 0-4           | Hasta 2 pts     |
| Edad (riesgo)         | —             | Hasta 2 pts     |

### Criterios de activación P1 inmediata

- Glasgow ≤ 8
- SpO₂ < 90%
- TAS < 70 mmHg
- FC > 150 o < 30 lpm
- FR > 35 o < 6 rpm
- Temperatura > 41°C o < 35°C
- Síntomas críticos: dolor torácico, síncope, hemorragia activa, déficit neurológico, quemaduras, anafilaxia

### Mapeo de score a prioridad

| Score NEWS2 | Prioridad | Tiempo máx. |
|-------------|-----------|-------------|
| ≥ 12        | P1 ROJO   | 5 min       |
| 7-11        | P2 NARANJA| 15 min      |
| 4-6         | P3 AMARILLO| 30 min     |
| 1-3         | P4 VERDE  | 120 min     |
| 0           | P4 VERDE  | 120 min     |

## 📦 Módulos Principales

### `backend/models.py`
- `SignosVitales` — Validación de parámetros fisiológicos con Pydantic
- `Paciente` — Entidad completa del paciente
- `ResultadoTriage` — Resultado del cálculo
- `RecursosHospital` — Estado de recursos en tiempo real
- `CATALOGO_SINTOMAS` — 12 síntomas con peso clínico

### `backend/triage_engine.py`
- `calcular_triage(paciente)` — Función principal del algoritmo
- `criterios_inmediatos()` — Detección de riesgo vital
- `ordenar_cola()` — Priorización con desempate por tiempo de espera
- `verificar_tiempos_espera()` — Alertas de espera excedida

### `backend/state_manager.py`
- `GestorUrgencias` — Singleton de estado de la sala
- `registrar_paciente()` — Ingreso a la cola
- `cambiar_estado()` — Transiciones con actualización de recursos
- `estadisticas()` — KPIs del turno
- `cargar_demo()` — 5 pacientes de ejemplo preconfigurados

### `frontend/components.py`
- `render_header()` — Métricas en tiempo real
- `render_sidebar_registro()` — Formulario completo de registro
- `render_cola_pacientes()` — Lista ordenada con filtros
- `render_detalle_paciente()` — Panel de acciones clínicas
- `render_recursos()` — Barras de ocupación hospitalaria
- `render_estadisticas()` — Distribución por prioridad

## 🧪 Tests

```bash
pytest tests/ -v --tb=short
```

Cobertura:
- Scores individuales NEWS2
- Criterios de activación inmediata
- Casos clínicos completos (P1 a P4)
- Reglas de negocio (anciano, pediátrico, GCS bajo)
- Ordenamiento de cola con desempate