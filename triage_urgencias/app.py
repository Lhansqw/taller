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
    page_title="ED Triage Board",
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
:root {
  --bg-deep: #0f172a;
  --bg-panel: #1e293b;
  --border: #334155;
  --text-muted: #94a3b8;
  --accent: #38bdf8;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.25rem; max-width: 1400px; }
h1 { font-size: 1.65rem !important; font-weight: 700 !important; letter-spacing: -0.02em; margin-bottom: 0.15rem !important; }
.app-tagline { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem; }
.p1 { color: #ef4444 !important; }
.p2 { color: #f97316 !important; }
.p3 { color: #eab308 !important; }
.p4 { color: #22c55e !important; }
.p5 { color: #6b7280 !important; }
.patient-card {
  border-left: 4px solid;
  padding: 12px 14px;
  margin: 0 0 10px 0;
  border-radius: 0 10px 10px 0;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-left-width: 4px;
  cursor: default;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.patient-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}
.card-p1 { border-left-color: #ef4444 !important; }
.card-p2 { border-left-color: #f97316 !important; }
.card-p3 { border-left-color: #eab308 !important; }
.card-p4 { border-left-color: #22c55e !important; }
.card-p5 { border-left-color: #6b7280 !important; }
div[data-testid="metric-container"] {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
}
div[data-testid="metric-container"] label {
  font-size: 0.78rem !important;
  color: var(--text-muted) !important;
}
.critical-alert {
  background: rgba(239,68,68,0.12);
  border: 1px solid rgba(239,68,68,0.55);
  border-radius: 10px;
  padding: 12px 16px;
  margin: 0 0 10px 0;
  font-size: 0.9rem;
  line-height: 1.45;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f172a 0%, #0c1222 100%);
  border-right: 1px solid var(--border);
}
.section-title-lg {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #94a3b8;
  text-transform: uppercase;
  margin: 0 0 10px 0;
}
.right-rail {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 14px;
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

    with st.sidebar:
        render_sidebar_registration(ed)

    st.markdown("# Emergency triage board")
    st.markdown(
        '<p class="app-tagline">Register new patients in the sidebar → pick someone from the queue → manage them in the panel on the right.</p>',
        unsafe_allow_html=True,
    )

    render_header(ed)

    overdue = ed.get_overdue_alerts()
    if overdue:
        st.markdown('<p class="section-title-lg">Needs attention</p>', unsafe_allow_html=True)
        render_alert_banners(overdue)

    queue_col, rail_col = st.columns([2.15, 1], gap="large")

    with queue_col:
        tabs = st.tabs(["Patient queue", "Shift statistics", "Activity log"])
        with tabs[0]:
            render_patient_queue(ed)
        with tabs[1]:
            render_statistics(ed)
        with tabs[2]:
            st.caption("Last 30 events · newest first")
            for entry in reversed(ed.audit_log[-30:]):
                st.caption(
                    f"`{entry['timestamp']}` **{entry['type']}** — {entry['description']}"
                )

    with rail_col:
        st.markdown("##### Capacity")
        st.caption("Available staff & beds (demo)")
        render_resources(ed)
        st.divider()
        st.markdown("##### Selected patient")
        pid = st.session_state.selected_patient_id
        if pid:
            render_patient_detail(ed, pid)
        else:
            st.info(
                "Choose a patient in the queue and tap **Open** to review vitals, "
                "add notes, and update status."
            )


if __name__ == "__main__":
    main()
