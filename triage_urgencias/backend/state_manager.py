"""
state_manager.py
In-memory ED department state.

Handles patient queue, hospital resources, audit log, and shift statistics.
Production would use a database (e.g. PostgreSQL).
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict
from backend.models import Patient, HospitalResources, PatientStatus
from backend.triage_engine import sort_queue, check_wait_time_violations


class EmergencyDepartment:
    """
    Holds full ED state. Persisted in Streamlit session_state across reruns.
    """

    def __init__(self):
        self.patients: List[Patient] = []
        self.resources: HospitalResources = HospitalResources()
        self.audit_log: List[Dict] = []
        self.shift_started_at: datetime = datetime.now()

    def register_patient(self, patient: Patient) -> Patient:
        """Assign ID, arrival time, waiting status."""
        patient.id = str(uuid.uuid4())[:8].upper()
        patient.arrival_time = datetime.now()
        patient.status = PatientStatus.WAITING
        patient.wait_minutes = 0.0
        self.patients.append(patient)
        self._log_action(
            "CHECK_IN",
            patient.id,
            f"Patient {patient.name} checked in as P{patient.priority}",
        )
        return patient

    def get_sorted_queue(self) -> List[Patient]:
        active = [
            p for p in self.patients if p.status not in (PatientStatus.DISCHARGED, PatientStatus.DECEASED)
        ]
        return sort_queue(active)

    def change_status(self, patient_id: str, new_status: str) -> Optional[Patient]:
        patient = self._find(patient_id)
        if not patient:
            return None
        previous = patient.status
        patient.status = new_status
        self._adjust_resources_for_transition(previous, new_status, patient)
        self._log_action(
            "STATUS",
            patient_id,
            f"{patient.name}: {previous} → {new_status}",
        )
        return patient

    def update_notes(self, patient_id: str, notes: str) -> bool:
        patient = self._find(patient_id)
        if not patient:
            return False
        patient.clinical_notes = notes
        return True

    def remove_patient(self, patient_id: str) -> bool:
        before = len(self.patients)
        self.patients = [p for p in self.patients if p.id != patient_id]
        return len(self.patients) < before

    def tick_wait_times(self, delta_minutes: float = 0.5):
        """Increase wait for patients still waiting. Call ~every 30s if simulating."""
        for p in self.patients:
            if p.status == PatientStatus.WAITING:
                p.wait_minutes += delta_minutes

    def get_overdue_alerts(self) -> List[dict]:
        waiting = [p for p in self.patients if p.status == PatientStatus.WAITING]
        return check_wait_time_violations(waiting)

    def statistics(self) -> Dict:
        total = len(self.patients)
        by_priority: Dict[str, int] = {}
        for pri in [1, 2, 3, 4, 5]:
            by_priority[f"P{pri}"] = len([x for x in self.patients if x.priority == pri])

        waiting = len([x for x in self.patients if x.status == PatientStatus.WAITING])
        in_progress = len([x for x in self.patients if x.status == PatientStatus.IN_PROGRESS])
        discharged = len([x for x in self.patients if x.status == PatientStatus.DISCHARGED])

        scores = [x.news2_score for x in self.patients if x.news2_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        wait_list = [x.wait_minutes for x in self.patients if x.status == PatientStatus.WAITING]
        avg_wait = round(sum(wait_list) / len(wait_list), 1) if wait_list else 0.0

        return {
            "total_patients": total,
            "by_priority": by_priority,
            "waiting": waiting,
            "in_progress": in_progress,
            "discharged_shift": discharged,
            "avg_news2": avg_score,
            "avg_wait_minutes": avg_wait,
            "active_overdue": len(self.get_overdue_alerts()),
            "shift_duration_min": round((datetime.now() - self.shift_started_at).seconds / 60, 1),
        }

    def _adjust_resources_for_transition(
        self, previous: str, new: str, p: Patient
    ):
        r = self.resources
        if new == PatientStatus.IN_PROGRESS:
            if p.priority and p.priority <= 2:
                r.icu_beds.available = max(0, r.icu_beds.available - 1)
            else:
                r.obs_beds.available = max(0, r.obs_beds.available - 1)
            r.physicians.available = max(0, r.physicians.available - 1)
        elif new == PatientStatus.TRANSFER:
            r.operating_rooms.available = max(0, r.operating_rooms.available - 1)
        elif new in (PatientStatus.DISCHARGED, PatientStatus.DECEASED):
            if previous == PatientStatus.IN_PROGRESS:
                if p.priority and p.priority <= 2:
                    r.icu_beds.available = min(
                        r.icu_beds.total, r.icu_beds.available + 1
                    )
                else:
                    r.obs_beds.available = min(
                        r.obs_beds.total, r.obs_beds.available + 1
                    )
                r.physicians.available = min(
                    r.physicians.total, r.physicians.available + 1
                )
            elif previous == PatientStatus.TRANSFER:
                r.operating_rooms.available = min(
                    r.operating_rooms.total, r.operating_rooms.available + 1
                )

    def _log_action(self, action_type: str, patient_id: str, description: str):
        self.audit_log.append(
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "type": action_type,
                "patient_id": patient_id,
                "description": description,
            }
        )

    def _find(self, patient_id: str) -> Optional[Patient]:
        return next((p for p in self.patients if p.id == patient_id), None)

    def load_demo(self):
        """Load sample patients for demo."""
        from backend.models import VitalSigns
        from backend.triage_engine import calculate_triage

        demos = [
            {
                "name": "John Miller",
                "age": 58,
                "sex": "M",
                "vs": VitalSigns(
                    heart_rate=142,
                    respiratory_rate=28,
                    systolic_bp=80,
                    temperature=36.2,
                    oxygen_saturation=88,
                    glasgow=13,
                    pain_nrs=9,
                ),
                "symptoms": ["chest_pain", "dyspnea"],
                "medical_history": "Prior MI. Profuse diaphoresis.",
                "wait_minutes": 8.0,
            },
            {
                "name": "Anna Brooks",
                "age": 34,
                "sex": "F",
                "vs": VitalSigns(
                    heart_rate=105,
                    respiratory_rate=22,
                    systolic_bp=110,
                    temperature=38.8,
                    oxygen_saturation=95,
                    glasgow=15,
                    pain_nrs=6,
                ),
                "symptoms": ["abdominal_pain", "nausea_vomiting"],
                "medical_history": "RLQ pain 6h. Possible appendicitis.",
                "wait_minutes": 9.0,
            },
            {
                "name": "Peter Gomez",
                "age": 72,
                "sex": "M",
                "vs": VitalSigns(
                    heart_rate=88,
                    respiratory_rate=18,
                    systolic_bp=130,
                    temperature=37.1,
                    oxygen_saturation=97,
                    glasgow=15,
                    pain_nrs=3,
                ),
                "symptoms": ["fever"],
                "medical_history": "Recurrent UTI. HTN.",
                "wait_minutes": 5.0,
            },
            {
                "name": "Lucy Torres",
                "age": 8,
                "sex": "F",
                "vs": VitalSigns(
                    heart_rate=130,
                    respiratory_rate=30,
                    systolic_bp=95,
                    temperature=39.5,
                    oxygen_saturation=92,
                    glasgow=14,
                    pain_nrs=7,
                ),
                "symptoms": ["dyspnea", "fever"],
                "medical_history": "Asthma exacerbation. No relief with home bronchodilator.",
                "wait_minutes": 12.0,
            },
            {
                "name": "Robert Lima",
                "age": 45,
                "sex": "M",
                "vs": VitalSigns(
                    heart_rate=76,
                    respiratory_rate=16,
                    systolic_bp=125,
                    temperature=36.8,
                    oxygen_saturation=99,
                    glasgow=15,
                    pain_nrs=4,
                ),
                "symptoms": ["possible_fracture"],
                "medical_history": "Bicycle fall. Right wrist pain.",
                "wait_minutes": 3.0,
            },
        ]

        for d in demos:
            p = Patient(
                name=d["name"],
                age=d["age"],
                sex=d["sex"],
                vital_signs=d["vs"],
                symptoms=d["symptoms"],
                medical_history=d.get("medical_history"),
            )
            result = calculate_triage(p)
            p.priority = result.priority
            p.news2_score = result.score
            p.triage_reasons = result.reasons
            self.register_patient(p)
            self._find(p.id).wait_minutes = d["wait_minutes"]
