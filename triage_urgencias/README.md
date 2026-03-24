#  ED Triage & Patient Flow Board

Academic demo — Python backend + Streamlit UI

##  Setup & run

```bash
pip install -r requirements.txt
streamlit run app.py
pytest tests/ -v
```

##  Layout

```
triage_urgencias/
├── app.py                 # Streamlit entrypoint
├── requirements.txt
├── backend/
│   ├── models.py          # Pydantic models (Patient, VitalSigns, …)
│   ├── triage_engine.py   # NEWS2 + Manchester-style triggers
│   └── state_manager.py   # In-memory queue, resources, audit log
├── frontend/
│   └── components.py      # Streamlit UI helpers
└── tests/
    └── test_triage_engine.py
```

##  Triage logic

NEWS2-style scoring plus immediate **P1** triggers:

### Immediate P1 triggers

- GCS ≤ 8  
- SpO₂ < 90%  
- SBP < 70 mmHg  
- HR > 150 or < 30  
- RR > 35 or < 6  
- Temperature > 41 °C or < 35 °C  
- Critical symptoms: chest pain, syncope, active bleed, neuro deficit, burns, severe allergy  

### Score → priority (simplified)

| NEWS2 total | Priority | Target wait |
|-------------|----------|-------------|
| ≥ 12        | P1 RED   | 5 min       |
| 7–11        | P2 ORANGE| 15 min      |
| 4–6         | P3 YELLOW| 30 min      |
| 1–3 or 0    | P4 GREEN | 120 min     |

##  Main modules

- **`backend/models.py`** — `VitalSigns`, `Patient`, `TriageResult`, `HospitalResources`, `SYMPTOM_CATALOG`, `PRIORITY_INFO`  
- **`backend/triage_engine.py`** — `calculate_triage`, `immediate_criteria`, `sort_queue`, `check_wait_time_violations`  
- **`backend/state_manager.py`** — `EmergencyDepartment`: register patients, change status, stats, `load_demo()`  
- **`frontend/components.py`** — header, registration form, queue, detail panel, resources, statistics  

##  Tests

```bash
pytest tests/ -v --tb=short
```

Covers NEWS2 sub-scores, immediate criteria, end-to-end cases (P1–P4), demographics (pediatric / geriatric), and queue ordering.
