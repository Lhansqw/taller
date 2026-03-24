"""
Unit tests for the triage engine.

Run: pytest tests/ -v
"""

from backend.models import Patient, VitalSigns
from backend.triage_engine import (
    calculate_triage,
    score_hr,
    score_rr,
    score_spo2,
    score_temp,
    score_sbp,
    score_gcs,
    immediate_criteria,
    sort_queue,
)


def make_critical_patient():
    """P1-style: ACS with shock physiology."""
    return Patient(
        name="Critical patient",
        age=60,
        sex="M",
        vital_signs=VitalSigns(
            heart_rate=145,
            respiratory_rate=30,
            systolic_bp=75,
            temperature=36.0,
            oxygen_saturation=87,
            glasgow=12,
            pain_nrs=9,
        ),
        symptoms=["chest_pain", "dyspnea"],
    )


def make_urgent_patient():
    """P2-style: acute abdomen."""
    return Patient(
        name="Urgent patient",
        age=35,
        sex="F",
        vital_signs=VitalSigns(
            heart_rate=108,
            respiratory_rate=22,
            systolic_bp=108,
            temperature=38.9,
            oxygen_saturation=95,
            glasgow=15,
            pain_nrs=7,
        ),
        symptoms=["abdominal_pain", "fever"],
    )


def make_low_acuity_patient():
    """P4-style: isolated injury, stable vitals."""
    return Patient(
        name="Low acuity patient",
        age=28,
        sex="M",
        vital_signs=VitalSigns(
            heart_rate=78,
            respiratory_rate=16,
            systolic_bp=122,
            temperature=36.7,
            oxygen_saturation=99,
            glasgow=15,
            pain_nrs=3,
        ),
        symptoms=["possible_fracture"],
    )


def make_pediatric_fever():
    """Pediatric patient with high fever."""
    return Patient(
        name="Pediatric fever",
        age=3,
        sex="M",
        vital_signs=VitalSigns(
            heart_rate=130,
            respiratory_rate=30,
            systolic_bp=90,
            temperature=39.8,
            oxygen_saturation=93,
            glasgow=14,
            pain_nrs=6,
        ),
        symptoms=["fever", "dyspnea"],
    )


class TestScoresNEWS2:
    def test_hr_normal(self):
        assert score_hr(75) == 0

    def test_hr_mild_tachycardia(self):
        assert score_hr(105) == 1

    def test_hr_severe_tachycardia(self):
        assert score_hr(135) == 3

    def test_hr_severe_bradycardia(self):
        assert score_hr(28) == 3

    def test_rr_normal(self):
        assert score_rr(16) == 0

    def test_rr_high(self):
        assert score_rr(26) == 3

    def test_spo2_normal(self):
        assert score_spo2(98) == 0

    def test_spo2_severe_hypoxemia(self):
        assert score_spo2(88) == 3

    def test_temp_normal(self):
        assert score_temp(36.8) == 0

    def test_temp_fever(self):
        assert score_temp(39.5) == 2

    def test_temp_hypothermia(self):
        assert score_temp(34.5) == 3

    def test_sbp_normal(self):
        assert score_sbp(120) == 0

    def test_sbp_shock_range(self):
        assert score_sbp(85) == 3

    def test_gcs_normal(self):
        assert score_gcs(15) == 0

    def test_gcs_severe(self):
        assert score_gcs(7) == 3


class TestImmediateCriteria:
    def test_low_gcs_triggers(self):
        vs = VitalSigns(
            heart_rate=80,
            respiratory_rate=16,
            systolic_bp=110,
            temperature=36.5,
            oxygen_saturation=97,
            glasgow=7,
            pain_nrs=0,
        )
        crit = immediate_criteria(vs, set(), 40)
        assert len(crit) > 0
        assert any("GCS" in c for c in crit)

    def test_hypoxemia_triggers(self):
        vs = VitalSigns(
            heart_rate=80,
            respiratory_rate=16,
            systolic_bp=110,
            temperature=36.5,
            oxygen_saturation=85,
            glasgow=15,
            pain_nrs=0,
        )
        crit = immediate_criteria(vs, set(), 40)
        assert any("SpO2" in c for c in crit)

    def test_critical_symptom_triggers(self):
        vs = VitalSigns(
            heart_rate=80,
            respiratory_rate=16,
            systolic_bp=120,
            temperature=36.8,
            oxygen_saturation=98,
            glasgow=15,
            pain_nrs=0,
        )
        crit = immediate_criteria(vs, {"syncope"}, 40)
        assert len(crit) > 0

    def test_stable_no_triggers(self):
        vs = VitalSigns(
            heart_rate=75,
            respiratory_rate=16,
            systolic_bp=120,
            temperature=36.8,
            oxygen_saturation=99,
            glasgow=15,
            pain_nrs=2,
        )
        crit = immediate_criteria(vs, set(), 35)
        assert len(crit) == 0


class TestCalculateTriage:
    def test_critical_is_p1(self):
        result = calculate_triage(make_critical_patient())
        assert result.priority == 1

    def test_urgent_at_most_p2(self):
        result = calculate_triage(make_urgent_patient())
        assert result.priority <= 2

    def test_low_acuity_at_least_p3(self):
        result = calculate_triage(make_low_acuity_patient())
        assert result.priority >= 3

    def test_pediatric_high_priority(self):
        result = calculate_triage(make_pediatric_fever())
        assert result.priority <= 2

    def test_result_has_reasons(self):
        result = calculate_triage(make_critical_patient())
        assert len(result.reasons) > 0

    def test_result_has_recommendations(self):
        result = calculate_triage(make_urgent_patient())
        assert len(result.recommendations) > 0

    def test_score_non_negative(self):
        result = calculate_triage(make_urgent_patient())
        assert result.score >= 0

    def test_priority_in_range(self):
        for p in [make_critical_patient(), make_urgent_patient(), make_low_acuity_patient()]:
            r = calculate_triage(p)
            assert 1 <= r.priority <= 5

    def test_gcs_forces_p1(self):
        patient = Patient(
            name="GCS test",
            age=50,
            sex="M",
            vital_signs=VitalSigns(
                heart_rate=80,
                respiratory_rate=18,
                systolic_bp=115,
                temperature=37.0,
                oxygen_saturation=96,
                glasgow=7,
                pain_nrs=0,
            ),
            symptoms=[],
        )
        assert calculate_triage(patient).priority == 1

    def test_geriatric_higher_than_young(self):
        vs_base = VitalSigns(
            heart_rate=92,
            respiratory_rate=20,
            systolic_bp=112,
            temperature=38.2,
            oxygen_saturation=95,
            glasgow=15,
            pain_nrs=4,
        )
        young = Patient(
            name="Young", age=35, sex="M", vital_signs=vs_base, symptoms=[]
        )
        older = Patient(
            name="Older", age=82, sex="M", vital_signs=vs_base, symptoms=[]
        )
        r_y = calculate_triage(young)
        r_o = calculate_triage(older)
        assert r_o.priority <= r_y.priority


class TestSortQueue:
    def test_p1_before_p4(self):
        p1 = make_critical_patient()
        p1.priority = 1
        p1.news2_score = 14
        p1.wait_minutes = 2

        p4 = make_low_acuity_patient()
        p4.priority = 4
        p4.news2_score = 2
        p4.wait_minutes = 60

        queue = sort_queue([p4, p1])
        assert queue[0].priority == 1

    def test_same_priority_longer_wait_first(self):
        from copy import deepcopy

        pa = make_urgent_patient()
        pa.priority = 2
        pa.news2_score = 8
        pa.wait_minutes = 14
        pb = deepcopy(pa)
        pb.name = "B"
        pb.wait_minutes = 5

        queue = sort_queue([pb, pa])
        assert queue[0].wait_minutes >= queue[1].wait_minutes
