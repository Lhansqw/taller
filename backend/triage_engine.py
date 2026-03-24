"""
triage_engine.py
Triage calculation engine.

Implements:
  - NHS NEWS2 (National Early Warning Score 2)
  - Immediate activation criteria (Manchester / ESI style)
  - Demographic risk factors
  - Final priority classification 1–5

Reference: Royal College of Physicians. NEWS2. London: RCP, 2017.
"""

from typing import Set, List, Tuple
from backend.models import (
    Patient,
    PatientStatus,
    VitalSigns,
    TriageResult,
    PRIORITY_INFO,
    SYMPTOM_CATALOG,
)


def score_hr(hr: int) -> int:
    """Heart rate → NEWS2 points."""
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def score_rr(rr: int) -> int:
    """Respiratory rate → NEWS2 points."""
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def score_spo2(spo2: int) -> int:
    """Oxygen saturation → NEWS2 points."""
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def score_temp(t: float) -> int:
    """Temperature → NEWS2 points."""
    if t <= 35.0:
        return 3
    if t <= 36.0:
        return 1
    if t <= 38.0:
        return 0
    if t <= 39.0:
        return 1
    return 2


def score_sbp(sbp: int) -> int:
    """Systolic blood pressure → NEWS2 points."""
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def score_gcs(gcs: int) -> int:
    """GCS → NEWS2 consciousness points."""
    if gcs >= 15:
        return 0
    if gcs >= 14:
        return 1
    if gcs >= 12:
        return 2
    return 3


def score_pain(nrs: int) -> int:
    """Pain NRS → extension (project-specific)."""
    if nrs >= 8:
        return 2
    if nrs >= 5:
        return 1
    return 0


CRITICAL_SYMPTOMS = {
    "chest_pain",
    "syncope",
    "hemorrhage",
    "neuro_deficit",
    "burns",
    "severe_allergy",
}


def immediate_criteria(vs: VitalSigns, symptoms: Set[str], _age: int) -> List[str]:
    """
    Criteria that mandate P1. Returns list of critical reason strings.
    """
    reasons: List[str] = []

    if vs.glasgow <= 8:
        reasons.append(f"🚨 GCS ≤8 ({vs.glasgow}): Severely impaired consciousness")
    if vs.oxygen_saturation < 90:
        reasons.append(
            f"🚨 SpO2 <90% ({vs.oxygen_saturation}%): Severe hypoxemia"
        )
    if vs.systolic_bp < 70:
        reasons.append(
            f"🚨 SBP <70 mmHg ({vs.systolic_bp}): Decompensated shock"
        )
    if vs.heart_rate > 150 or vs.heart_rate < 30:
        reasons.append(
            f"🚨 HR {vs.heart_rate} bpm: Critical hemodynamic instability"
        )
    if vs.respiratory_rate > 35 or vs.respiratory_rate < 6:
        reasons.append(
            f"🚨 RR {vs.respiratory_rate} /min: Respiratory failure"
        )
    if vs.temperature > 41.0:
        reasons.append(f"🚨 Temperature {vs.temperature} °C: Extreme hyperthermia")
    if vs.temperature < 35.0:
        reasons.append(f"🚨 Temperature {vs.temperature} °C: Severe hypothermia")

    critical_present = CRITICAL_SYMPTOMS & symptoms
    if critical_present:
        labels = [s.replace("_", " ").title() for s in critical_present]
        reasons.append(f"🚨 Critical symptom(s): {', '.join(labels)}")

    return reasons


def demographic_factors(age: int, symptoms: Set[str]) -> Tuple[int, List[str]]:
    """Extra points and reasons from age-related risk."""
    points = 0
    reasons: List[str] = []

    if age >= 80:
        points += 2
        reasons.append(
            "📌 Geriatric (≥80y): higher physiological vulnerability"
        )
    elif age >= 65:
        points += 1
        reasons.append("📌 Older adult (≥65y): risk of rapid deterioration")
    elif age <= 5:
        points += 2
        reasons.append("📌 Pediatric (≤5y): limited physiological reserve")
    elif age <= 14:
        points += 1
        reasons.append("📌 Pediatric (≤14y)")

    return points, reasons


def noncritical_symptom_points(symptoms: Set[str]) -> float:
    """Weighted contribution of non-critical symptoms."""
    total = 0.0
    catalog = {s.code: s for s in SYMPTOM_CATALOG}
    for code in symptoms:
        sym = catalog.get(code)
        if sym and not sym.is_critical:
            total += sym.weight * 0.5
    return total


def priority_from_score(score: float) -> int:
    """Map total NEWS2-style score to triage priority."""
    if score >= 12:
        return 1
    if score >= 7:
        return 2
    if score >= 4:
        return 3
    if score >= 1:
        return 4
    return 4


def calculate_triage(patient: Patient) -> TriageResult:
    """
    Main triage algorithm.

    1. Immediate criteria → force P1 if any
    2. Physiologic NEWS2 score
    3. Demographics
    4. Non-critical symptoms
    5. Final priority (most urgent wins)
    6. Reasons and recommendations
    """
    vs = patient.vital_signs
    symptoms = set(patient.symptoms)
    reasons: List[str] = []

    crit = immediate_criteria(vs, symptoms, patient.age)
    force_p1 = len(crit) > 0
    reasons.extend(crit)

    score_base = (
        score_hr(vs.heart_rate)
        + score_rr(vs.respiratory_rate)
        + score_spo2(vs.oxygen_saturation)
        + score_temp(vs.temperature)
        + score_sbp(vs.systolic_bp)
        + score_gcs(vs.glasgow)
        + score_pain(vs.pain_nrs)
    )

    extra_demo, demo_reasons = demographic_factors(patient.age, symptoms)
    reasons.extend(demo_reasons)

    sym_pts = noncritical_symptom_points(symptoms)
    total_score = score_base + extra_demo + sym_pts

    priority_from_news2 = priority_from_score(total_score)
    final_priority = 1 if force_p1 else priority_from_news2

    if total_score > 0:
        reasons.append(
            f"📊 NEWS2 total: {total_score:.1f} pts "
            f"(HR:{score_hr(vs.heart_rate)} RR:{score_rr(vs.respiratory_rate)} "
            f"SpO2:{score_spo2(vs.oxygen_saturation)} "
            f"T°:{score_temp(vs.temperature)} "
            f"BP:{score_sbp(vs.systolic_bp)} GCS:{score_gcs(vs.glasgow)})"
        )

    if len(reasons) == 0:
        reasons.append("✅ Stable — no major urgency criteria detected")

    info = PRIORITY_INFO[final_priority]

    return TriageResult(
        priority=final_priority,
        label=info["label"],
        color_hex=info["color_hex"],
        max_wait_minutes=info["max_wait"],
        score=round(total_score, 1),
        reasons=reasons,
        recommendations=info["recommendation"],
        vital_alerts=vs.alert_messages(),
    )


def sort_queue(patients: List[Patient]) -> List[Patient]:
    """
    Sort queue by: priority (P1 first), relative wait vs max allowed,
    then higher NEWS2 score.
    """

    def sort_key(p: Patient):
        info = PRIORITY_INFO.get(p.priority or 4, {})
        max_wait = info.get("max_wait") or 999
        wait_ratio = p.wait_minutes / max_wait if max_wait else 0
        return (p.priority or 4, -wait_ratio, -(p.news2_score or 0))

    return sorted(patients, key=sort_key)


def check_wait_time_violations(patients: List[Patient]) -> List[dict]:
    """Patients who exceeded max wait for their priority."""
    alerts = []
    for p in patients:
        if p.status != PatientStatus.WAITING:
            continue
        info = PRIORITY_INFO.get(p.priority or 4, {})
        max_wait = info.get("max_wait")
        if max_wait and p.wait_minutes > max_wait:
            alerts.append(
                {
                    "patient_id": p.id,
                    "name": p.name,
                    "priority": p.priority,
                    "wait_minutes": p.wait_minutes,
                    "max_wait": max_wait,
                    "over_by_min": round(p.wait_minutes - max_wait, 1),
                }
            )
    return alerts
