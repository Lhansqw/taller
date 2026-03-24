"""
app.py
Punto de entrada de la aplicación Streamlit.

Sistema de Triage y Flujo de Sala de Urgencias — Hospital
Ejecutar con:  streamlit run app.py
"""

import streamlit as st
from frontend.components import (
    render_header,
    render_sidebar_registro,
    render_cola_pacientes,
    render_detalle_paciente,
    render_recursos,
    render_estadisticas,
    render_alertas
)
from backend.state_manager import GestorUrgencias

# ─────────────────────────────────────────────
# CONFIGURACIÓN STREAMLIT
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Triage — Sala de Urgencias",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Sistema de Triage Hospitalario — Taller Académico"
    }
)

# ─────────────────────────────────────────────
# CSS GLOBAL
# ─────────────────────────────────────────────

st.markdown("""
<style>
    /* Ocultar menú de Streamlit */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* Colores de prioridad */
    .p1 { color: #ef4444 !important; }
    .p2 { color: #f97316 !important; }
    .p3 { color: #eab308 !important; }
    .p4 { color: #22c55e !important; }
    .p5 { color: #6b7280 !important; }

    /* Tarjetas de paciente */
    .patient-card {
        border-left: 5px solid;
        padding: 10px 14px;
        margin: 6px 0;
        border-radius: 0 8px 8px 0;
        background: #1e293b;
        cursor: pointer;
        transition: transform 0.15s;
    }

    .patient-card:hover { transform: translateX(3px); }
    .card-p1 { border-color: #ef4444; }
    .card-p2 { border-color: #f97316; }
    .card-p3 { border-color: #eab308; }
    .card-p4 { border-color: #22c55e; }
    .card-p5 { border-color: #6b7280; }

    /* Badges de estado */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: bold;
    }

    /* Métricas personalizadas */
    div[data-testid="metric-container"] {
        background: #1e293b;
        border: 1px solid #1e2d45;
        border-radius: 8px;
        padding: 10px;
    }

    /* Alertas */
    .alerta-critica {
        background: rgba(239,68,68,0.1);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 5px 0;
        animation: parpadeo 1.5s infinite;
    }

    @keyframes parpadeo {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #0f172a; }

    /* Títulos de sección */
    .section-title {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        color: #64748b;
        text-transform: uppercase;
        padding-bottom: 6px;
        border-bottom: 1px solid #1e2d45;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ESTADO DE SESIÓN
# ─────────────────────────────────────────────

def init_session():
    """Inicializa el estado de sesión si es la primera carga."""
    if "gestor" not in st.session_state:
        st.session_state.gestor = GestorUrgencias()

    if "paciente_seleccionado_id" not in st.session_state:
        st.session_state.paciente_seleccionado_id = None

    if "filtro_prioridad" not in st.session_state:
        st.session_state.filtro_prioridad = "Todos"

    if "pagina_activa" not in st.session_state:
        st.session_state.pagina_activa = "cola"  # cola | estadisticas | historial

    if "demo_cargado" not in st.session_state:
        st.session_state.gestor.cargar_demo()
        st.session_state.demo_cargado = True


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    init_session()
    gestor: GestorUrgencias = st.session_state.gestor

    # Header principal
    render_header(gestor)

    # Alertas de tiempo de espera (zona crítica)
    alertas = gestor.obtener_alertas()
    if alertas:
        render_alertas(alertas)

    # Layout de 3 columnas
    col_izq, col_centro, col_der = st.columns([1.2, 2, 1], gap="small")

    with col_izq:
        render_sidebar_registro(gestor)

    with col_centro:
        pagina = st.session_state.pagina_activa
        tabs = st.tabs(["🏥 Cola de Atención", "📊 Estadísticas", "📋 Historial"])

        with tabs[0]:
            render_cola_pacientes(gestor)

        with tabs[1]:
            render_estadisticas(gestor)

        with tabs[2]:
            st.subheader("Historial de Acciones")
            for accion in reversed(gestor.historial[-30:]):
                st.caption(f"`{accion['timestamp']}` **{accion['tipo']}** — {accion['descripcion']}")

    with col_der:
        render_recursos(gestor)
        st.divider()

        pid = st.session_state.paciente_seleccionado_id
        if pid:
            render_detalle_paciente(gestor, pid)
        else:
            st.info("👆 Selecciona un paciente para ver su detalle")


if __name__ == "__main__":
    main()