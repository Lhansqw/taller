"""
components.py
Componentes de UI reutilizables para Streamlit.

Cada función render_* corresponde a un bloque visual independiente
que puede reusarse en distintas partes de la aplicación.
"""

import streamlit as st
from datetime import datetime
from typing import List, Optional
from backend.models import Paciente, PRIORIDAD_INFO, CATALOGO_SINTOMAS
from backend.triage_engine import calcular_triage
from backend.state_manager import GestorUrgencias


# ─── COLORES POR PRIORIDAD ───────────────────
COLOR_MAP = {1: "#ef4444", 2: "#f97316", 3: "#eab308", 4: "#22c55e", 5: "#6b7280"}
EMOJI_MAP = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚫"}
LABEL_MAP = {
    1: "P1 ROJO", 2: "P2 NARANJA",
    3: "P3 AMARILLO", 4: "P4 VERDE", 5: "P5 NEGRO"
}


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

def render_header(gestor: GestorUrgencias):
    stats = gestor.estadisticas()
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("🚨 Críticos (P1)", stats["por_prioridad"].get("P1", 0))
    col2.metric("⏳ En Espera",     stats["en_espera"])
    col3.metric("👨‍⚕️ En Atención",  stats["en_atencion"])
    col4.metric("✅ Altas Turno",    stats["altas_turno"])
    col5.metric("⚠️ Alertas",        stats["alertas_activas"],
                delta=None if stats["alertas_activas"] == 0 else "⚠️ Supera tiempo",
                delta_color="inverse")

    st.divider()


# ─────────────────────────────────────────────
# ALERTAS CRÍTICAS
# ─────────────────────────────────────────────

def render_alertas(alertas: List[dict]):
    for a in alertas:
        st.markdown(f"""
        <div class="alerta-critica">
            {EMOJI_MAP.get(a['prioridad'], '⚠️')}
            <strong>{a['nombre']}</strong>
            &nbsp;|&nbsp; {LABEL_MAP.get(a['prioridad'], '')}
            &nbsp;|&nbsp; Espera: <strong>{a['minutos_espera']:.0f} min</strong>
            (máx. {a['tiempo_max']} min — exceso: +{a['exceso_min']} min)
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# FORMULARIO DE REGISTRO + TRIAGE
# ─────────────────────────────────────────────

def render_sidebar_registro(gestor: GestorUrgencias):
    st.markdown('<div class="section-title">📋 Registro de Paciente</div>', unsafe_allow_html=True)

    with st.form("form_registro", clear_on_submit=True):
        nombre = st.text_input("Nombre Completo *", placeholder="Ej: María García")

        col_a, col_b = st.columns(2)
        edad = col_a.number_input("Edad *", min_value=0, max_value=120, value=30)
        sexo = col_b.selectbox("Sexo", ["M", "F", "O"],
                                format_func=lambda x: {"M":"Masculino","F":"Femenino","O":"Otro"}[x])

        st.markdown("**🩺 Signos Vitales**")
        col1, col2 = st.columns(2)
        fc   = col1.number_input("FC (lpm) *", 0, 300, 75)
        fr   = col2.number_input("FR (rpm) *", 0, 60, 16)
        tas  = col1.number_input("TAS (mmHg) *", 0, 300, 120)
        temp = col2.number_input("Temp (°C) *", 28.0, 45.0, 36.5, step=0.1)
        spo2 = col1.number_input("SpO₂ (%) *", 0, 100, 98)
        gcs  = col2.number_input("Glasgow (3-15)", 3, 15, 15)
        dolor= st.slider("Dolor EVA (0-10)", 0, 10, 0)

        st.markdown("**🔍 Síntomas**")
        sintomas_sel = []
        cols = st.columns(2)
        for i, sym in enumerate(CATALOGO_SINTOMAS):
            if cols[i % 2].checkbox(sym.descripcion, key=f"sym_{sym.codigo}"):
                sintomas_sel.append(sym.codigo)

        antecedentes = st.text_area("Antecedentes / Mecanismo", height=60,
                                     placeholder="Medicación, alergias, motivo...")

        submitted = st.form_submit_button("⚡ CALCULAR TRIAGE", type="primary", use_container_width=True)

    if submitted:
        if not nombre:
            st.error("⚠️ El nombre es obligatorio.")
            return

        from backend.models import SignosVitales, Paciente
        sv = SignosVitales(
            frecuencia_cardiaca=fc,
            frecuencia_respiratoria=fr,
            tension_arterial_sistolica=tas,
            temperatura=temp,
            saturacion_oxigeno=spo2,
            glasgow=gcs,
            dolor_eva=dolor
        )
        paciente = Paciente(
            nombre=nombre, edad=edad, sexo=sexo,
            signos_vitales=sv,
            sintomas=sintomas_sel,
            antecedentes=antecedentes or None
        )

        resultado = calcular_triage(paciente)
        paciente.prioridad = resultado.prioridad
        paciente.score_news2 = resultado.score
        paciente.razones_triage = resultado.razones

        # Mostrar resultado antes de confirmar
        st.session_state["triage_pendiente"] = paciente
        st.session_state["triage_resultado"] = resultado
        st.rerun()

    # Confirmar ingreso del paciente con resultado de triage
    if "triage_pendiente" in st.session_state:
        _mostrar_resultado_triage(gestor)

    # Botón demo
    if st.button("🔄 Cargar Paciente Demo", use_container_width=True):
        st.info("Recarga la página para ver los demos precargados.")


def _mostrar_resultado_triage(gestor: GestorUrgencias):
    """Muestra el popup de resultado de triage y permite confirmar el ingreso."""
    p = st.session_state["triage_pendiente"]
    r = st.session_state["triage_resultado"]
    color = COLOR_MAP[r.prioridad]
    emoji = EMOJI_MAP[r.prioridad]

    st.divider()
    st.markdown(f"### {emoji} Resultado Triage")

    st.markdown(f"""
    <div style="border:2px solid {color}; border-radius:10px; padding:14px; background:{color}15; margin:8px 0;">
        <div style="color:{color}; font-size:1.2rem; font-weight:800;">{r.label}</div>
        <div style="font-size:0.82rem; margin-top:4px;">Score NEWS2: <strong>{r.score}</strong></div>
        <div style="font-size:0.78rem; color:#94a3b8; margin-top:6px;">
            {'<br>'.join(r.razones[:4])}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    if col1.button("✅ Confirmar Ingreso", type="primary", use_container_width=True):
        gestor.registrar_paciente(p)
        del st.session_state["triage_pendiente"]
        del st.session_state["triage_resultado"]
        st.success(f"✅ {p.nombre} ingresado como {r.label}")
        st.rerun()

    if col2.button("❌ Cancelar", use_container_width=True):
        del st.session_state["triage_pendiente"]
        del st.session_state["triage_resultado"]
        st.rerun()


# ─────────────────────────────────────────────
# COLA DE PACIENTES
# ─────────────────────────────────────────────

def render_cola_pacientes(gestor: GestorUrgencias):
    cola = gestor.obtener_cola_ordenada()

    # Filtros
    filtro = st.selectbox(
        "Filtrar por prioridad",
        ["Todos", "P1 - Rojo", "P2 - Naranja", "P3 - Amarillo", "P4 - Verde"],
        key="filtro_cola",
        label_visibility="collapsed"
    )

    filtro_map = {"P1 - Rojo": 1, "P2 - Naranja": 2, "P3 - Amarillo": 3, "P4 - Verde": 4}
    if filtro != "Todos":
        cola = [p for p in cola if p.prioridad == filtro_map[filtro]]

    if not cola:
        st.info("📋 No hay pacientes en esta categoría.")
        return

    for p in cola:
        _render_patient_card(p, gestor)


def _render_patient_card(p: Paciente, gestor: GestorUrgencias):
    """Tarjeta individual de paciente en la cola."""
    color = COLOR_MAP.get(p.prioridad or 4, "#6b7280")
    emoji = EMOJI_MAP.get(p.prioridad or 4, "⚫")
    estado_badge = {
        "espera":    ("🟡 EN ESPERA",  "#eab30833"),
        "atencion":  ("🔵 EN ATENCIÓN","#3b82f633"),
        "traslado":  ("🟣 TRASLADO",   "#a855f733"),
        "alta":      ("🟢 ALTA",       "#22c55e33"),
    }.get(p.estado, ("⚪ DESCONOCIDO", "#ffffff11"))

    sv = p.signos_vitales
    alertas_vitales = sv.alertas()

    # Color de espera
    info = PRIORIDAD_INFO.get(p.prioridad or 4, {})
    tiempo_max = info.get("tiempo_max") or 999
    pct_espera = (p.minutos_espera / tiempo_max) * 100 if tiempo_max else 0
    tiempo_color = "#ef4444" if pct_espera > 100 else "#eab308" if pct_espera > 70 else "#64748b"

    with st.container():
        st.markdown(f"""
        <div class="patient-card card-p{p.prioridad}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <span style="color:{color}; font-weight:800; font-size:0.85rem;">{emoji} {p.id} — {LABEL_MAP.get(p.prioridad,'')}</span><br>
                    <span style="font-size:1rem; font-weight:700;">{p.nombre}</span>
                    <span style="color:#94a3b8; font-size:0.78rem;"> · {p.edad}a · {p.sexo}</span><br>
                    <span style="background:{estado_badge[1]}; padding:1px 7px; border-radius:4px; font-size:0.68rem;">{estado_badge[0]}</span>
                </div>
                <div style="text-align:right;">
                    <span style="color:{tiempo_color}; font-family:monospace; font-size:0.85rem; font-weight:700;">{p.minutos_espera:.0f}min</span><br>
                    <span style="color:#64748b; font-size:0.7rem;">Score: {p.score_news2 or 0}</span>
                </div>
            </div>
            <div style="margin-top:6px; display:flex; gap:6px; flex-wrap:wrap;">
                <code style="font-size:0.65rem;">FC {sv.frecuencia_cardiaca}</code>
                <code style="font-size:0.65rem;">SpO2 {sv.saturacion_oxigeno}%</code>
                <code style="font-size:0.65rem;">TA {sv.tension_arterial_sistolica}</code>
                <code style="font-size:0.65rem;">T {sv.temperatura}°C</code>
                {'<span style="color:#ef4444; font-size:0.65rem;">⚠️ Alertas vitales</span>' if alertas_vitales else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(f"Ver detalle →", key=f"sel_{p.id}", use_container_width=False):
            st.session_state.paciente_seleccionado_id = p.id
            st.rerun()


# ─────────────────────────────────────────────
# DETALLE DEL PACIENTE SELECCIONADO
# ─────────────────────────────────────────────

def render_detalle_paciente(gestor: GestorUrgencias, paciente_id: str):
    """Panel derecho con detalle completo y acciones sobre el paciente."""
    paciente = next((p for p in gestor.pacientes if p.id == paciente_id), None)
    if not paciente:
        st.warning("Paciente no encontrado.")
        return

    st.markdown('<div class="section-title">🔍 Detalle Paciente</div>', unsafe_allow_html=True)
    color = COLOR_MAP.get(paciente.prioridad or 4, "#6b7280")
    emoji = EMOJI_MAP.get(paciente.prioridad or 4, "⚫")

    st.markdown(f"""
    <div style="border:1px solid {color}; border-radius:10px; padding:12px; margin-bottom:10px;">
        <div style="color:{color}; font-weight:800;">{emoji} {LABEL_MAP.get(paciente.prioridad,'')}</div>
        <div style="font-size:1.1rem; font-weight:700; margin-top:2px;">{paciente.nombre}</div>
        <div style="color:#94a3b8; font-size:0.75rem;">{paciente.edad} años · {paciente.sexo} · Score: {paciente.score_news2}</div>
    </div>
    """, unsafe_allow_html=True)

    # Signos vitales
    sv = paciente.signos_vitales
    col1, col2 = st.columns(2)
    col1.metric("FC (lpm)", sv.frecuencia_cardiaca, delta=None,
                help="Normal: 60-100 lpm")
    col2.metric("SpO₂ (%)", f"{sv.saturacion_oxigeno}%")
    col1.metric("TAS (mmHg)", sv.tension_arterial_sistolica)
    col2.metric("Temperatura", f"{sv.temperatura}°C")
    col1.metric("FR (rpm)", sv.frecuencia_respiratoria)
    col2.metric("Glasgow", f"{sv.glasgow}/15")

    # Razones del triage
    if paciente.razones_triage:
        with st.expander("📊 Razones del Triage", expanded=False):
            for r in paciente.razones_triage:
                st.caption(r)

    # Antecedentes
    if paciente.antecedentes:
        st.caption(f"📝 {paciente.antecedentes}")

    # Notas clínicas
    notas = st.text_area("Notas Clínicas",
                          value=paciente.notas_clinicas or "",
                          height=70, key=f"notes_{paciente.id}")
    if st.button("💾 Guardar Notas", key=f"save_notes_{paciente.id}"):
        gestor.actualizar_notas(paciente.id, notas)
        st.success("Notas guardadas.")

    # Acciones de estado
    st.markdown("**Acciones**")
    if st.button("👨‍⚕️ Iniciar Atención", key=f"act_{paciente.id}", use_container_width=True):
        gestor.cambiar_estado(paciente.id, "atencion")
        st.rerun()

    if st.button("🚑 Traslado UCI/Qx", key=f"tras_{paciente.id}", use_container_width=True):
        gestor.cambiar_estado(paciente.id, "traslado")
        st.rerun()

    if st.button("✅ Dar Alta", key=f"alta_{paciente.id}", use_container_width=True):
        gestor.cambiar_estado(paciente.id, "alta")
        st.session_state.paciente_seleccionado_id = None
        st.rerun()

    if st.button("🗑️ Retirar de Lista", key=f"del_{paciente.id}", type="secondary", use_container_width=True):
        gestor.eliminar_paciente(paciente.id)
        st.session_state.paciente_seleccionado_id = None
        st.rerun()


# ─────────────────────────────────────────────
# RECURSOS HOSPITALARIOS
# ─────────────────────────────────────────────

def render_recursos(gestor: GestorUrgencias):
    st.markdown('<div class="section-title">🏗️ Recursos</div>', unsafe_allow_html=True)
    r = gestor.recursos

    def bar_recurso(nombre: str, disp: int, total: int):
        pct = disp / total if total else 0
        color = "#ef4444" if pct < 0.3 else "#eab308" if pct < 0.6 else "#22c55e"
        st.markdown(f"""
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-bottom:2px;">
                <span>{nombre}</span>
                <span style="font-family:monospace;">{disp}/{total}</span>
            </div>
            <div style="background:#1e2d45; border-radius:4px; height:6px;">
                <div style="background:{color}; width:{pct*100:.0f}%; height:6px; border-radius:4px; transition:width 0.4s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    bar_recurso("Camas UCI",      r.camas_uci.disponibles,  r.camas_uci.total)
    bar_recurso("Camas Obs.",     r.camas_obs.disponibles,  r.camas_obs.total)
    bar_recurso("Médicos",        r.medicos.disponibles,    r.medicos.total)
    bar_recurso("Enfermeros",     r.enfermeros.disponibles, r.enfermeros.total)
    bar_recurso("Quirófanos",     r.quirofano.disponibles,  r.quirofano.total)
    bar_recurso("Ventiladores",   r.ventiladores.disponibles, r.ventiladores.total)


# ─────────────────────────────────────────────
# ESTADÍSTICAS
# ─────────────────────────────────────────────

def render_estadisticas(gestor: GestorUrgencias):
    stats = gestor.estadisticas()

    st.subheader("📊 Estadísticas del Turno")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pacientes",      stats["total_pacientes"])
    col2.metric("Score Promedio NEWS2", stats["score_promedio"])
    col3.metric("Espera Promedio",      f"{stats['tiempo_espera_promedio_min']} min")

    st.markdown("**Distribución por Prioridad**")
    for p_num in [1, 2, 3, 4, 5]:
        key = f"P{p_num}"
        count = stats["por_prioridad"].get(key, 0)
        color = COLOR_MAP.get(p_num, "#6b7280")
        emoji = EMOJI_MAP.get(p_num, "⚫")
        total = stats["total_pacientes"] or 1
        pct = count / total

        st.markdown(f"""
        <div style="margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between; font-size:0.78rem; margin-bottom:2px;">
                <span>{emoji} {LABEL_MAP[p_num]}</span>
                <strong style="color:{color};">{count}</strong>
            </div>
            <div style="background:#1e2d45; border-radius:4px; height:8px;">
                <div style="background:{color}; width:{pct*100:.0f}%; height:8px; border-radius:4px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)