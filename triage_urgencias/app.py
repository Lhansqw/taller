"""
app.py
Streamlit entrypoint — ED triage & flow board.

Run: streamlit run app.py
"""

import streamlit as st
from frontend.components import (
    render_header,
    render_sidebar_registration,
    render_patient_queue,
    render_patient_detail,
    render_resources,
    render_statistics,
    render_alert_banners,
)
from backend.state_manager import EmergencyDepartment

st.set_page_config(
    page_title="Triage — Emergency Department",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Hospital triage board — academic demo",
    },
)

st.html("""<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.p1 { color: #ef4444 !important; }
.p2 { color: #f97316 !important; }
.p3 { color: #eab308 !important; }
.p4 { color: #22c55e !important; }
.p5 { color: #6b7280 !important; }
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
.badge {
display: inline-block;
padding: 2px 8px;
border-radius: 4px;
font-size: 0.72rem;
font-weight: bold;
}
div[data-testid="metric-container"] {
background: #1e293b;
border: 1px solid #1e2d45;
border-radius: 8px;
padding: 10px;
}
.critical-alert {
background: rgba(239,68,68,0.1);
border: 1px solid #ef4444;
border-radius: 8px;
padding: 10px 14px;
margin: 5px 0;
animation: blink 1.5s infinite;
}
@keyframes blink {
0%, 100% { opacity: 1; }
50% { opacity: 0.6; }
}
section[data-testid="stSidebar"] { background: #0f172a; }
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
</style>""")


def init_session():
    if "department" not in st.session_state:
        st.session_state.department = EmergencyDepartment()

    if "selected_patient_id" not in st.session_state:
        st.session_state.selected_patient_id = None

    if "demo_loaded" not in st.session_state:
        st.session_state.department.load_demo()
        st.session_state.demo_loaded = True


def main():
    init_session()
    ed: EmergencyDepartment = st.session_state.department

    render_header(ed)

    overdue = ed.get_overdue_alerts()
    if overdue:
        render_alert_banners(overdue)

    left, center, right = st.columns([1.2, 2, 1], gap="small")

    with left:
        render_sidebar_registration(ed)

    with center:
        tabs = st.tabs(["🏥 Queue", "📊 Statistics", "📋 Activity log"])

        with tabs[0]:
            render_patient_queue(ed)

        with tabs[1]:
            render_statistics(ed)

        with tabs[2]:
            st.subheader("Activity log")
            for entry in reversed(ed.audit_log[-30:]):
                st.caption(
                    f"`{entry['timestamp']}` **{entry['type']}** — {entry['description']}"
                )

    with right:
        render_resources(ed)
        st.divider()

        pid = st.session_state.selected_patient_id
        if pid:
            render_patient_detail(ed, pid)
        else:
            st.info("👆 Select a patient to see details")


if __name__ == "__main__":
    main()
