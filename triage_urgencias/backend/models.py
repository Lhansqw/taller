"""
models.py
Triage data models (Pydantic).

Core entities: Patient, VitalSigns, TriageResult, Resource.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from enum import IntEnum
from datetime import datetime


class TriagePriority(IntEnum):
    """Manchester / ESI-style priority scale."""
    P1_RED = 1      # Immediate (<5 min) — life threat
    P2_ORANGE = 2   # Emergent (<15 min) — severe compromise
    P3_YELLOW = 3   # Less urgent (<30 min)
    P4_GREEN = 4    # Non-urgent (<120 min)
    P5_BLACK = 5    # Expectant — overwhelming injury


class PatientStatus:
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    TRANSFER = "transfer"
    DISCHARGED = "discharged"
    DECEASED = "deceased"


class VitalSigns(BaseModel):
    """
    Vital signs with clinical reference ranges.
    Values outside normal ranges trigger alerts.
    """
    heart_rate: int = Field(..., ge=0, le=300, description="Beats per minute")
    respiratory_rate: int = Field(..., ge=0, le=60, description="Breaths per minute")
    systolic_bp: int = Field(..., ge=0, le=300, description="mmHg systolic")
    temperature: float = Field(..., ge=28.0, le=45.0, description="Celsius")
    oxygen_saturation: int = Field(..., ge=0, le=100, description="SpO2 %")
    glasgow: int = Field(15, ge=3, le=15, description="Glasgow Coma Scale")
    pain_nrs: int = Field(0, ge=0, le=10, description="Numeric pain scale 0–10")

    @field_validator("heart_rate")
    @classmethod
    def _heart_rate_band(cls, v: int) -> int:
        if v < 30 or v > 200:
            pass  # handled as critical criterion in triage engine
        return v

    def alert_messages(self) -> List[str]:
        """Parameters outside typical normal range (informational)."""
        alerts: List[str] = []
        if self.heart_rate > 120 or self.heart_rate < 50:
            alerts.append(f"⚠️ Abnormal HR: {self.heart_rate} bpm")
        if self.respiratory_rate > 25 or self.respiratory_rate < 10:
            alerts.append(f"⚠️ Abnormal RR: {self.respiratory_rate} /min")
        if self.systolic_bp < 100 or self.systolic_bp > 180:
            alerts.append(f"⚠️ Abnormal SBP: {self.systolic_bp} mmHg")
        if self.temperature > 38.5 or self.temperature < 36.0:
            alerts.append(f"⚠️ Temperature: {self.temperature} °C")
        if self.oxygen_saturation < 95:
            alerts.append(f"⚠️ Low SpO2: {self.oxygen_saturation}%")
        if self.glasgow < 15:
            alerts.append(f"⚠️ Reduced GCS: {self.glasgow}/15")
        return alerts


class Symptom(BaseModel):
    code: str
    description: str
    weight: float
    is_critical: bool


SYMPTOM_CATALOG: List[Symptom] = [
    Symptom(code="chest_pain", description="Chest pain", weight=4.0, is_critical=True),
    Symptom(code="dyspnea", description="Dyspnea / breathing difficulty", weight=3.0, is_critical=True),
    Symptom(code="syncope", description="Syncope / loss of consciousness", weight=4.0, is_critical=True),
    Symptom(code="hemorrhage", description="Active bleeding", weight=4.0, is_critical=True),
    Symptom(code="neuro_deficit", description="Neurologic deficit", weight=4.0, is_critical=True),
    Symptom(code="burns", description="Burns", weight=3.0, is_critical=True),
    Symptom(code="severe_allergy", description="Severe allergic reaction", weight=3.0, is_critical=True),
    Symptom(code="trauma", description="Trauma / polytrauma", weight=3.0, is_critical=False),
    Symptom(code="fever", description="High fever", weight=2.0, is_critical=False),
    Symptom(code="abdominal_pain", description="Abdominal pain", weight=2.0, is_critical=False),
    Symptom(code="nausea_vomiting", description="Nausea / vomiting", weight=1.0, is_critical=False),
    Symptom(code="possible_fracture", description="Possible fracture", weight=2.0, is_critical=False),
]


class Patient(BaseModel):
    """Primary patient entity."""
    id: Optional[str] = None
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=120)
    sex: str = Field(default="M", pattern=r"^[MFO]$")
    vital_signs: VitalSigns
    symptoms: List[str] = Field(default_factory=list, description="Present symptom codes")
    medical_history: Optional[str] = None
    arrival_time: Optional[datetime] = None
    priority: Optional[int] = None
    news2_score: Optional[float] = None
    status: str = PatientStatus.WAITING
    wait_minutes: float = 0.0
    triage_reasons: List[str] = Field(default_factory=list)
    clinical_notes: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class TriageResult(BaseModel):
    priority: int
    label: str
    color_hex: str
    max_wait_minutes: Optional[int]
    score: float
    reasons: List[str]
    recommendations: List[str]
    vital_alerts: List[str]


PRIORITY_INFO = {
    1: {
        "label": "P1 — RED — IMMEDIATE",
        "color_hex": "#ef4444",
        "max_wait": 5,
        "recommendation": [
            "Activate emergency response", "Continuous monitoring",
            "Large-bore IV access", "Prepare ICU",
        ],
    },
    2: {
        "label": "P2 — ORANGE — URGENT",
        "color_hex": "#f97316",
        "max_wait": 15,
        "recommendation": [
            "Immediate medical evaluation", "Monitor every 5 min",
            "Peripheral IV access", "ECG if chest pain",
        ],
    },
    3: {
        "label": "P3 — YELLOW — LESS URGENT",
        "color_hex": "#eab308",
        "max_wait": 30,
        "recommendation": [
            "Evaluate within 30 min", "Repeat vital signs",
            "Analgesia if indicated",
        ],
    },
    4: {
        "label": "P4 — GREEN — NON-URGENT",
        "color_hex": "#22c55e",
        "max_wait": 120,
        "recommendation": [
            "General waiting area", "Reassess if worse",
            "May wait in waiting room",
        ],
    },
    5: {
        "label": "P5 — BLACK — EXPECTANT",
        "color_hex": "#6b7280",
        "max_wait": None,
        "recommendation": [
            "Palliative care only", "Conserve scarce resources", "Family support",
        ],
    },
}


class Resource(BaseModel):
    name: str
    available: int
    total: int

    @property
    def availability_pct(self) -> float:
        return (self.available / self.total) * 100 if self.total > 0 else 0

    @property
    def load_band(self) -> str:
        pct = self.availability_pct
        if pct >= 80:
            return "critical"
        if pct >= 50:
            return "moderate"
        return "available"


class HospitalResources(BaseModel):
    icu_beds: Resource = Resource(name="ICU beds", available=2, total=5)
    obs_beds: Resource = Resource(name="Observation beds", available=3, total=5)
    physicians: Resource = Resource(name="Physicians", available=3, total=4)
    nurses: Resource = Resource(name="Nurses", available=4, total=6)
    operating_rooms: Resource = Resource(name="Operating rooms", available=1, total=2)
    ventilators: Resource = Resource(name="Ventilators", available=2, total=5)
