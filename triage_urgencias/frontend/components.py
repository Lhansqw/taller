"""
components.py
Reusable Streamlit UI blocks — layout tuned for sidebar intake + main queue + detail rail.
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
    1: "P1 · Immediate",
    2: "P2 · Urgent",
    3: "P3 · Less urgent",
    4: "P4 · Non-urgent",
    5: "P5 · Expectant",
}


def render_header(ed: EmergencyDepartment):
    stats = ed.statistics()
    st.caption("Shift snapshot")
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    c1.metric("P1 critical", stats["by_priority"].get("P1", 0))
    c2.metric("Waiting", stats["waiting"])
    c3.metric("In progress", stats["in_progress"])
    c4.metric("Discharged", stats["discharged_shift"])
    c5.metric(
        "Overdue",
        stats["active_overdue"],
        delta=None if stats["active_overdue"] == 0 else "Past target",
        delta_color="inverse",
    )


def render_alert_banners(alerts: List[dict]):
    for a in alerts:
        name = escape(str(a["name"]))
        pri = escape(LABEL_MAP.get(a["priority"], ""))
        st.html(
            f"""<div class="critical-alert">
<strong style="color:#fecaca;">Wait time exceeded</strong><br>
<span style="color:#e2e8f0;">{name}</span>
<span style="color:#94a3b8;"> · {pri}</span><br>
<span style="color:#cbd5e1; font-size:0.85rem;">Waiting <strong>{a['wait_minutes']:.0f} min</strong> (target {a['max_wait']} min, +{a['over_by_min']} min over)</span>
</div>"""
        )


def render_sidebar_registration(ed: EmergencyDepartment):
    st.markdown("### New patient")
    st.caption("Fill vitals, then calculate triage. You can confirm check-in after review.")

    with st.form("registration_form", clear_on_submit=True):
        st.markdown("**Identity**")
        name = st.text_input("Full name", placeholder="e.g. Jane Doe", label_visibility="visible")
        c_a, c_b = st.columns(2)
        age = c_a.number_input("Age", min_value=0, max_value=120, value=30)
        sex = c_b.selectbox(
            "Sex",
            ["M", "F", "O"],
            format_func=lambda x: {"M": "Male", "F": "Female", "O": "Other"}[x],
        )

        with st.expander("Vital signs", expanded=True):
            c1, c2 = st.columns(2)
            hr = c1.number_input("Heart rate (bpm)", 0, 300, 75)
            rr = c2.number_input("Resp. rate (/min)", 0, 60, 16)
            sbp = c1.number_input("Systolic BP (mmHg)", 0, 300, 120)
            temp = c2.number_input("Temp (°C)", 28.0, 45.0, 36.5, step=0.1)
            spo2 = c1.number_input("SpO₂ (%)", 0, 100, 98)
            gcs = c2.number_input("GCS", 3, 15, 15)
            pain = st.slider("Pain (0–10)", 0, 10, 0)

        with st.expander("Symptoms (check all that apply)", expanded=False):
            selected: List[str] = []
            cols = st.columns(2)
            for i, sym in enumerate(SYMPTOM_CATALOG):
                if cols[i % 2].checkbox(sym.description, key=f"sym_{sym.code}"):
                    selected.append(sym.code)

        history = st.text_area(
            "History & chief complaint",
            height=72,
            placeholder="Medications, allergies, what happened…",
        )

        submitted = st.form_submit_button(
            "Calculate triage", type="primary", use_container_width=True
        )

    if submitted:
        if not name or not str(name).strip():
            st.error("Please enter the patient’s name.")
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
            name=name.strip(),
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

    st.divider()
    st.caption("Demo data")
    if st.button("Reset demo list", use_container_width=True, help="Reload the page to reload built-in demo patients"):
        st.info("Refresh the browser page to restore demo patients.")


def _show_pending_triage_confirmation(ed: EmergencyDepartment):
    p: Patient = st.session_state["pending_triage_patient"]
    r = st.session_state["pending_triage_result"]
    color = COLOR_MAP[r.priority]

    st.markdown("---")
    st.markdown("**Suggested acuity**")
    reasons_html = "<br>".join(escape(x) for x in r.reasons[:5])
    label_e = escape(r.label)
    st.html(
        f"""<div style="border:1px solid {color}; border-radius:10px; padding:12px; background:{color}12; margin:8px 0;">
<div style="color:{color}; font-size:1.05rem; font-weight:700;">{label_e}</div>
<div style="font-size:0.8rem; color:#94a3b8; margin-top:4px;">NEWS2 total: <strong style="color:#e2e8f0;">{r.score}</strong></div>
<div style="font-size:0.78rem; color:#cbd5e1; margin-top:8px; line-height:1.4;">{reasons_html}</div>
</div>"""
    )

    c1, c2 = st.columns(2)
    if c1.button("Add to queue", type="primary", use_container_width=True):
        ed.register_patient(p)
        del st.session_state["pending_triage_patient"]
        del st.session_state["pending_triage_result"]
        st.success(f"{p.name} added to the board.")
        st.rerun()

    if c2.button("Discard", use_container_width=True):
        del st.session_state["pending_triage_patient"]
        del st.session_state["pending_triage_result"]
        st.rerun()


def render_patient_queue(ed: EmergencyDepartment):
    queue = ed.get_sorted_queue()

    st.markdown("### Who is waiting")
    st.caption("Highest acuity and longest waits appear first. Use the filter to focus one color.")

    filt = st.selectbox(
        "Show priority",
        ["All levels", "P1 — Red only", "P2 — Orange", "P3 — Yellow", "P4 — Green"],
        key="queue_filter",
    )
    fmap = {
        "P1 — Red only": 1,
        "P2 — Orange": 2,
        "P3 — Yellow": 3,
        "P4 — Green": 4,
    }
    if filt != "All levels":
        queue = [p for p in queue if p.priority == fmap[filt]]

    if not queue:
        st.info("No patients match this filter.")
        return

    for p in queue:
        _patient_card(p, ed)


def _patient_card(p: Patient, ed: EmergencyDepartment):
    color = COLOR_MAP.get(p.priority or 4, "#6b7280")
    emoji = EMOJI_MAP.get(p.priority or 4, "⚫")
    badges = {
        PatientStatus.WAITING: ("Waiting", "#eab30833"),
        PatientStatus.IN_PROGRESS: ("In progress", "#3b82f633"),
        PatientStatus.TRANSFER: ("Transfer", "#a855f733"),
        PatientStatus.DISCHARGED: ("Discharged", "#22c55e33"),
    }.get(p.status, ("Other", "#ffffff11"))

    vs = p.vital_signs
    vit_alerts = vs.alert_messages()

    info = PRIORITY_INFO.get(p.priority or 4, {})
    max_wait = info.get("max_wait") or 999
    wait_pct = (p.wait_minutes / max_wait) * 100 if max_wait else 0
    wait_color = (
        "#f87171" if wait_pct > 100 else "#fbbf24" if wait_pct > 70 else "#94a3b8"
    )

    pri = p.priority if p.priority is not None else 4
    pid_lbl = f"{escape(str(p.id))} · {escape(LABEL_MAP.get(p.priority, ''))}"
    name_e = escape(p.name)
    badge_lbl = badges[0]
    alert_span = (
        '<span style="color:#f87171; font-size:0.7rem;">⚠ Vital flags</span>'
        if vit_alerts
        else ""
    )

    st.html(
        f"""<div class="patient-card card-p{pri}">
<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
<div style="min-width:0;">
<div style="color:{color}; font-weight:700; font-size:0.8rem; margin-bottom:2px;">{emoji} {pid_lbl}</div>
<div style="font-size:1.02rem; font-weight:600; color:#f1f5f9;">{name_e}<span style="color:#94a3b8; font-weight:500;"> · {p.age}y · {escape(p.sex)}</span></div>
<div style="margin-top:6px;"><span style="background:{badges[1]}; padding:2px 8px; border-radius:6px; font-size:0.72rem; color:#e2e8f0;">{badge_lbl}</span></div>
</div>
<div style="text-align:right; flex-shrink:0;">
<div style="color:{wait_color}; font-family:ui-monospace,monospace; font-size:0.9rem; font-weight:600;">{p.wait_minutes:.0f} min</div>
<div style="color:#64748b; font-size:0.72rem;">NEWS2 {p.news2_score or 0}</div>
</div>
</div>
<div style="margin-top:10px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
<span style="font-size:0.72rem; color:#64748b; background:#0f172a; padding:2px 6px; border-radius:4px;">HR {vs.heart_rate}</span>
<span style="font-size:0.72rem; color:#64748b; background:#0f172a; padding:2px 6px; border-radius:4px;">SpO₂ {vs.oxygen_saturation}%</span>
<span style="font-size:0.72rem; color:#64748b; background:#0f172a; padding:2px 6px; border-radius:4px;">BP {vs.systolic_bp}</span>
<span style="font-size:0.72rem; color:#64748b; background:#0f172a; padding:2px 6px; border-radius:4px;">T {vs.temperature}°C</span>
{alert_span}
</div>
</div>"""
    )

    if st.button(
        "Open patient",
        key=f"sel_{p.id}",
        use_container_width=True,
        type="secondary",
    ):
        st.session_state.selected_patient_id = p.id
        st.rerun()


def render_patient_detail(ed: EmergencyDepartment, patient_id: str):
    patient = next((p for p in ed.patients if p.id == patient_id), None)
    if not patient:
        st.warning("That patient is no longer on the board.")
        return

    color = COLOR_MAP.get(patient.priority or 4, "#6b7280")
    emoji = EMOJI_MAP.get(patient.priority or 4, "⚫")
    lbl = escape(LABEL_MAP.get(patient.priority, ""))
    nom = escape(patient.name)
    st.html(
        f"""<div style="border:1px solid {color}; border-radius:10px; padding:12px; margin-bottom:12px; background:{color}0d;">
<div style="color:{color}; font-weight:700; font-size:0.85rem;">{emoji} {lbl}</div>
<div style="font-size:1.1rem; font-weight:600; color:#f8fafc; margin-top:4px;">{nom}</div>
<div style="color:#94a3b8; font-size:0.8rem; margin-top:2px;">{patient.age} yrs · {escape(patient.sex)} · NEWS2 {patient.news2_score}</div>
</div>"""
    )

    st.markdown("**Vitals**")
    vs = patient.vital_signs
    c1, c2 = st.columns(2)
    c1.metric("HR", f"{vs.heart_rate} bpm")
    c2.metric("SpO₂", f"{vs.oxygen_saturation}%")
    c1.metric("BP", f"{vs.systolic_bp} mmHg")
    c2.metric("RR", f"{vs.respiratory_rate} /min")
    c1.metric("Temp", f"{vs.temperature} °C")
    c2.metric("GCS", str(vs.glasgow))

    if patient.triage_reasons:
        with st.expander("Why this acuity?", expanded=False):
            for line in patient.triage_reasons:
                st.caption(line)

    if patient.medical_history:
        st.markdown("**History**")
        st.caption(patient.medical_history)

    st.divider()
    st.markdown("**Notes**")
    notes = st.text_area(
        "Clinical notes",
        value=patient.clinical_notes or "",
        height=80,
        key=f"notes_{patient.id}",
        label_visibility="collapsed",
        placeholder="Handoff details, plan, follow-up…",
    )
    if st.button("Save notes", key=f"save_notes_{patient.id}", use_container_width=True):
        ed.update_notes(patient.id, notes)
        st.success("Saved.")

    st.divider()
    st.markdown("**Next step**")
    st.caption("Move the patient through the visit as their status changes.")

    b1, b2 = st.columns(2)
    if b1.button("Start care", key=f"act_{patient.id}", use_container_width=True):
        ed.change_status(patient.id, PatientStatus.IN_PROGRESS)
        st.rerun()
    if b2.button("Transfer", key=f"tras_{patient.id}", use_container_width=True):
        ed.change_status(patient.id, PatientStatus.TRANSFER)
        st.rerun()

    b3, b4 = st.columns(2)
    if b3.button("Discharge", key=f"dc_{patient.id}", use_container_width=True):
        ed.change_status(patient.id, PatientStatus.DISCHARGED)
        st.session_state.selected_patient_id = None
        st.rerun()
    if b4.button(
        "Remove",
        key=f"del_{patient.id}",
        use_container_width=True,
        type="secondary",
    ):
        ed.remove_patient(patient.id)
        st.session_state.selected_patient_id = None
        st.rerun()


def render_resources(ed: EmergencyDepartment):
    r = ed.resources

    def bar_row(label: str, avail: int, total: int):
        pct = avail / total if total else 0
        bar_color = "#f87171" if pct < 0.3 else "#fbbf24" if pct < 0.6 else "#4ade80"
        st.html(
            f"""<div style="margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:4px; color:#cbd5e1;">
<span>{escape(label)}</span>
<span style="font-family:ui-monospace,monospace; color:#94a3b8;">{avail} / {total}</span>
</div>
<div style="background:#0f172a; border-radius:6px; height:8px; overflow:hidden;">
<div style="background:{bar_color}; width:{pct*100:.0f}%; height:8px; border-radius:6px;"></div>
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
    st.markdown("### Shift overview")
    st.caption(f"Running ~{stats['shift_duration_min']} min this session (demo clock).")

    c1, c2, c3 = st.columns(3)
    c1.metric("Patients on board", stats["total_patients"])
    c2.metric("Mean NEWS2", stats["avg_news2"])
    c3.metric("Mean wait (waiting)", f"{stats['avg_wait_minutes']} min")

    st.markdown("**Mix by acuity**")
    for p_num in [1, 2, 3, 4, 5]:
        key = f"P{p_num}"
        count = stats["by_priority"].get(key, 0)
        color = COLOR_MAP.get(p_num, "#6b7280")
        emoji = EMOJI_MAP.get(p_num, "⚫")
        total = stats["total_patients"] or 1
        frac = count / total
        lbl = escape(LABEL_MAP[p_num])
        st.html(
            f"""<div style="margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:3px;">
<span>{emoji} {lbl}</span>
<strong style="color:{color};">{count}</strong>
</div>
<div style="background:#0f172a; border-radius:6px; height:8px;">
<div style="background:{color}; width:{frac*100:.0f}%; height:8px; border-radius:6px;"></div>
</div>
</div>"""
        )
