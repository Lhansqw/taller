"""
components.py
Reusable Streamlit UI blocks.
"""

import streamlit as st
from html import escape
from typing import List
from backend.models import Patient, PRIORITY_INFO, SYMPTOM_CATALOG
from backend.triage_engine import calculate_triage
from backend.state_manager import EmergencyDepartment
from backend.models import PatientStatus


COLOR_MAP = {1: "#ef4444", 2: "#f97316", 3: "#eab308", 4: "#22c55e", 5: "#6b7280"}
EMOJI_MAP = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚫"}
LABEL_MAP = {
    1: "P1 RED",
    2: "P2 ORANGE",
    3: "P3 YELLOW",
    4: "P4 GREEN",
    5: "P5 BLACK",
}


def render_header(ed: EmergencyDepartment):
    stats = ed.statistics()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🚨 Critical (P1)", stats["by_priority"].get("P1", 0))
    c2.metric("⏳ Waiting", stats["waiting"])
    c3.metric("👨‍⚕️ In progress", stats["in_progress"])
    c4.metric("✅ Discharged (shift)", stats["discharged_shift"])
    c5.metric(
        "⚠️ Overdue",
        stats["active_overdue"],
        delta=None if stats["active_overdue"] == 0 else "Past target wait",
        delta_color="inverse",
    )
    st.divider()


def render_alert_banners(alerts: List[dict]):
    for a in alerts:
        name = escape(str(a["name"]))
        st.html(
            f"""<div class="critical-alert">
{EMOJI_MAP.get(a['priority'], '⚠️')}
<strong>{name}</strong>
&nbsp;|&nbsp; {escape(LABEL_MAP.get(a['priority'], ''))}
&nbsp;|&nbsp; Wait: <strong>{a['wait_minutes']:.0f} min</strong>
(target {a['max_wait']} min — over by +{a['over_by_min']} min)
</div>"""
        )


def render_sidebar_registration(ed: EmergencyDepartment):
    st.html('<div class="section-title">📋 Patient registration</div>')

    with st.form("registration_form", clear_on_submit=True):
        name = st.text_input("Full name *", placeholder="e.g. Jane Doe")
        c_a, c_b = st.columns(2)
        age = c_a.number_input("Age *", min_value=0, max_value=120, value=30)
        sex = c_b.selectbox(
            "Sex",
            ["M", "F", "O"],
            format_func=lambda x: {"M": "Male", "F": "Female", "O": "Other"}[x],
        )

        st.markdown("**🩺 Vital signs**")
        c1, c2 = st.columns(2)
        hr = c1.number_input("HR (bpm) *", 0, 300, 75)
        rr = c2.number_input("RR (/min) *", 0, 60, 16)
        sbp = c1.number_input("SBP (mmHg) *", 0, 300, 120)
        temp = c2.number_input("Temp (°C) *", 28.0, 45.0, 36.5, step=0.1)
        spo2 = c1.number_input("SpO₂ (%) *", 0, 100, 98)
        gcs = c2.number_input("GCS (3–15)", 3, 15, 15)
        pain = st.slider("Pain NRS (0–10)", 0, 10, 0)

        st.markdown("**🔍 Symptoms**")
        selected: List[str] = []
        cols = st.columns(2)
        for i, sym in enumerate(SYMPTOM_CATALOG):
            if cols[i % 2].checkbox(sym.description, key=f"sym_{sym.code}"):
                selected.append(sym.code)

        history = st.text_area(
            "History / mechanism",
            height=60,
            placeholder="Meds, allergies, chief complaint…",
        )

        submitted = st.form_submit_button(
            "⚡ CALCULATE TRIAGE", type="primary", use_container_width=True
        )

    if submitted:
        if not name:
            st.error("⚠️ Name is required.")
            return
        from backend.models import VitalSigns, Patient

        vs = VitalSigns(
            heart_rate=hr,
            respiratory_rate=rr,
            systolic_bp=sbp,
            temperature=temp,
            oxygen_saturation=spo2,
            glasgow=gcs,
            pain_nrs=pain,
        )
        patient = Patient(
            name=name,
            age=age,
            sex=sex,
            vital_signs=vs,
            symptoms=selected,
            medical_history=history or None,
        )
        result = calculate_triage(patient)
        patient.priority = result.priority
        patient.news2_score = result.score
        patient.triage_reasons = result.reasons
        st.session_state["pending_triage_patient"] = patient
        st.session_state["pending_triage_result"] = result
        st.rerun()

    if "pending_triage_patient" in st.session_state:
        _show_pending_triage_confirmation(ed)

    if st.button("🔄 Reload demo patients", use_container_width=True):
        st.info("Reload the page to see preloaded demo patients again.")


def _show_pending_triage_confirmation(ed: EmergencyDepartment):
    p: Patient = st.session_state["pending_triage_patient"]
    r = st.session_state["pending_triage_result"]
    color = COLOR_MAP[r.priority]
    emoji = EMOJI_MAP[r.priority]

    st.divider()
    st.markdown(f"### {emoji} Triage result")

    reasons_html = "<br>".join(escape(x) for x in r.reasons[:4])
    label_e = escape(r.label)
    st.html(
        f"""<div style="border:2px solid {color}; border-radius:10px; padding:14px; background:{color}15; margin:8px 0;">
<div style="color:{color}; font-size:1.2rem; font-weight:800;">{label_e}</div>
<div style="font-size:0.82rem; margin-top:4px;">NEWS2 total: <strong>{r.score}</strong></div>
<div style="font-size:0.78rem; color:#94a3b8; margin-top:6px;">{reasons_html}</div>
</div>"""
    )

    c1, c2 = st.columns(2)
    if c1.button("✅ Confirm check-in", type="primary", use_container_width=True):
        ed.register_patient(p)
        del st.session_state["pending_triage_patient"]
        del st.session_state["pending_triage_result"]
        st.success(f"✅ {p.name} checked in as {r.label}")
        st.rerun()

    if c2.button("❌ Cancel", use_container_width=True):
        del st.session_state["pending_triage_patient"]
        del st.session_state["pending_triage_result"]
        st.rerun()


def render_patient_queue(ed: EmergencyDepartment):
    queue = ed.get_sorted_queue()

    filt = st.selectbox(
        "Filter by priority",
        ["All", "P1 — Red", "P2 — Orange", "P3 — Yellow", "P4 — Green"],
        key="queue_filter",
        label_visibility="collapsed",
    )
    fmap = {"P1 — Red": 1, "P2 — Orange": 2, "P3 — Yellow": 3, "P4 — Green": 4}
    if filt != "All":
        queue = [p for p in queue if p.priority == fmap[filt]]

    if not queue:
        st.info("📋 No patients in this category.")
        return

    for p in queue:
        _patient_card(p, ed)


def _patient_card(p: Patient, ed: EmergencyDepartment):
    color = COLOR_MAP.get(p.priority or 4, "#6b7280")
    emoji = EMOJI_MAP.get(p.priority or 4, "⚫")
    badges = {
        PatientStatus.WAITING: ("🟡 WAITING", "#eab30833"),
        PatientStatus.IN_PROGRESS: ("🔵 IN PROGRESS", "#3b82f633"),
        PatientStatus.TRANSFER: ("🟣 TRANSFER", "#a855f733"),
        PatientStatus.DISCHARGED: ("🟢 DISCHARGED", "#22c55e33"),
    }.get(p.status, ("⚪ UNKNOWN", "#ffffff11"))

    vs = p.vital_signs
    vit_alerts = vs.alert_messages()

    info = PRIORITY_INFO.get(p.priority or 4, {})
    max_wait = info.get("max_wait") or 999
    wait_pct = (p.wait_minutes / max_wait) * 100 if max_wait else 0
    wait_color = (
        "#ef4444" if wait_pct > 100 else "#eab308" if wait_pct > 70 else "#64748b"
    )

    pri = p.priority if p.priority is not None else 4
    pid_lbl = f"{escape(str(p.id))} — {escape(LABEL_MAP.get(p.priority, ''))}"
    name_e = escape(p.name)
    badge_lbl = badges[0]
    alert_span = (
        '<span style="color:#ef4444; font-size:0.65rem;">⚠️ Vital sign alerts</span>'
        if vit_alerts
        else ""
    )

    with st.container():
        st.html(
            f"""<div class="patient-card card-p{pri}">
<div style="display:flex; justify-content:space-between; align-items:flex-start;">
<div>
<span style="color:{color}; font-weight:800; font-size:0.85rem;">{emoji} {pid_lbl}</span><br>
<span style="font-size:1rem; font-weight:700;">{name_e}</span>
<span style="color:#94a3b8; font-size:0.78rem;"> · {p.age}y · {escape(p.sex)}</span><br>
<span style="background:{badges[1]}; padding:1px 7px; border-radius:4px; font-size:0.68rem;">{badge_lbl}</span>
</div>
<div style="text-align:right;">
<span style="color:{wait_color}; font-family:monospace; font-size:0.85rem; font-weight:700;">{p.wait_minutes:.0f}min</span><br>
<span style="color:#64748b; font-size:0.7rem;">Score: {p.news2_score or 0}</span>
</div>
</div>
<div style="margin-top:6px; display:flex; gap:6px; flex-wrap:wrap;">
<code style="font-size:0.65rem;">HR {vs.heart_rate}</code>
<code style="font-size:0.65rem;">SpO2 {vs.oxygen_saturation}%</code>
<code style="font-size:0.65rem;">BP {vs.systolic_bp}</code>
<code style="font-size:0.65rem;">T {vs.temperature}&#176;C</code>
{alert_span}
</div>
</div>"""
        )

        if st.button("View detail →", key=f"sel_{p.id}", use_container_width=False):
            st.session_state.selected_patient_id = p.id
            st.rerun()


def render_patient_detail(ed: EmergencyDepartment, patient_id: str):
    patient = next((p for p in ed.patients if p.id == patient_id), None)
    if not patient:
        st.warning("Patient not found.")
        return

    st.html('<div class="section-title">🔍 Patient detail</div>')
    color = COLOR_MAP.get(patient.priority or 4, "#6b7280")
    emoji = EMOJI_MAP.get(patient.priority or 4, "⚫")

    lbl = escape(LABEL_MAP.get(patient.priority, ""))
    nom = escape(patient.name)
    st.html(
        f"""<div style="border:1px solid {color}; border-radius:10px; padding:12px; margin-bottom:10px;">
<div style="color:{color}; font-weight:800;">{emoji} {lbl}</div>
<div style="font-size:1.1rem; font-weight:700; margin-top:2px;">{nom}</div>
<div style="color:#94a3b8; font-size:0.75rem;">{patient.age} years · {escape(patient.sex)} · Score: {patient.news2_score}</div>
</div>"""
    )

    vs = patient.vital_signs
    c1, c2 = st.columns(2)
    c1.metric("HR (bpm)", vs.heart_rate, delta=None, help="Typical: 60–100 bpm")
    c2.metric("SpO₂ (%)", f"{vs.oxygen_saturation}%")
    c1.metric("SBP (mmHg)", vs.systolic_bp)
    c2.metric("Temperature", f"{vs.temperature} °C")
    c1.metric("RR (/min)", vs.respiratory_rate)
    c2.metric("GCS", f"{vs.glasgow}/15")

    if patient.triage_reasons:
        with st.expander("📊 Triage rationale", expanded=False):
            for line in patient.triage_reasons:
                st.caption(line)

    if patient.medical_history:
        st.caption(f"📝 {patient.medical_history}")

    notes = st.text_area(
        "Clinical notes",
        value=patient.clinical_notes or "",
        height=70,
        key=f"notes_{patient.id}",
    )
    if st.button("💾 Save notes", key=f"save_notes_{patient.id}"):
        ed.update_notes(patient.id, notes)
        st.success("Notes saved.")

    st.markdown("**Actions**")
    if st.button(
        "👨‍⚕️ Start care",
        key=f"act_{patient.id}",
        use_container_width=True,
    ):
        ed.change_status(patient.id, PatientStatus.IN_PROGRESS)
        st.rerun()

    if st.button(
        "🚑 Transfer ICU/OR",
        key=f"tras_{patient.id}",
        use_container_width=True,
    ):
        ed.change_status(patient.id, PatientStatus.TRANSFER)
        st.rerun()

    if st.button(
        "✅ Discharge",
        key=f"dc_{patient.id}",
        use_container_width=True,
    ):
        ed.change_status(patient.id, PatientStatus.DISCHARGED)
        st.session_state.selected_patient_id = None
        st.rerun()

    if st.button(
        "🗑️ Remove from board",
        key=f"del_{patient.id}",
        type="secondary",
        use_container_width=True,
    ):
        ed.remove_patient(patient.id)
        st.session_state.selected_patient_id = None
        st.rerun()


def render_resources(ed: EmergencyDepartment):
    st.html('<div class="section-title">🏗️ Resources</div>')
    r = ed.resources

    def bar_row(label: str, avail: int, total: int):
        pct = avail / total if total else 0
        bar_color = "#ef4444" if pct < 0.3 else "#eab308" if pct < 0.6 else "#22c55e"
        st.html(
            f"""<div style="margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; font-size:0.72rem; margin-bottom:2px;">
<span>{escape(label)}</span>
<span style="font-family:monospace;">{avail}/{total}</span>
</div>
<div style="background:#1e2d45; border-radius:4px; height:6px;">
<div style="background:{bar_color}; width:{pct*100:.0f}%; height:6px; border-radius:4px; transition:width 0.4s;"></div>
</div>
</div>"""
        )

    bar_row(r.icu_beds.name, r.icu_beds.available, r.icu_beds.total)
    bar_row(r.obs_beds.name, r.obs_beds.available, r.obs_beds.total)
    bar_row(r.physicians.name, r.physicians.available, r.physicians.total)
    bar_row(r.nurses.name, r.nurses.available, r.nurses.total)
    bar_row(r.operating_rooms.name, r.operating_rooms.available, r.operating_rooms.total)
    bar_row(r.ventilators.name, r.ventilators.available, r.ventilators.total)


def render_statistics(ed: EmergencyDepartment):
    stats = ed.statistics()
    st.subheader("📊 Shift statistics")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total patients", stats["total_patients"])
    c2.metric("Average NEWS2", stats["avg_news2"])
    c3.metric("Average wait", f"{stats['avg_wait_minutes']} min")

    st.markdown("**By priority**")
    for p_num in [1, 2, 3, 4, 5]:
        key = f"P{p_num}"
        count = stats["by_priority"].get(key, 0)
        color = COLOR_MAP.get(p_num, "#6b7280")
        emoji = EMOJI_MAP.get(p_num, "⚫")
        total = stats["total_patients"] or 1
        frac = count / total

        lbl = escape(LABEL_MAP[p_num])
        st.html(
            f"""<div style="margin-bottom:6px;">
<div style="display:flex; justify-content:space-between; font-size:0.78rem; margin-bottom:2px;">
<span>{emoji} {lbl}</span>
<strong style="color:{color};">{count}</strong>
</div>
<div style="background:#1e2d45; border-radius:4px; height:8px;">
<div style="background:{color}; width:{frac*100:.0f}%; height:8px; border-radius:4px;"></div>
</div>
</div>"""
        )
