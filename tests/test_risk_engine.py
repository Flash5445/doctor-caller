"""
tests for risk assessment engine.

tests rule-based risk analysis of patient vital signs.
"""

import sys
from datetime import datetime, timedelta

sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

import pytest
from backend.models.vitals import Vital
from backend.services.risk_engine import (
    assess_risk,
    _analyze_heart_rate,
    _analyze_spo2,
    _analyze_blood_pressure,
    _analyze_respiratory_rate,
    _analyze_temperature,
    _check_sustained_condition,
    _aggregate_risk_level,
)
from backend.repositories.vitals_repository import VitalsRepository
from backend.config import get_db_session


def _create_mock_vital(
    patient_id: str = "TEST_001",
    timestamp: datetime = None,
    heart_rate: float = 75.0,
    respiratory_rate: float = 16.0,
    body_temperature: float = 36.8,
    spo2: float = 98.0,
    systolic_bp: int = 120,
    diastolic_bp: int = 80,
) -> Vital:
    """
    create a mock vital record for testing.

    args:
        patient_id: patient identifier
        timestamp: vital timestamp (defaults to now)
        heart_rate: heart rate in bpm
        respiratory_rate: respiratory rate in breaths/min
        body_temperature: temperature in celsius
        spo2: oxygen saturation percentage
        systolic_bp: systolic blood pressure in mmhg
        diastolic_bp: diastolic blood pressure in mmhg

    returns:
        vital instance with specified values
    """
    vital = Vital()
    vital.patient_id = patient_id
    vital.timestamp = timestamp or datetime.utcnow()
    vital.heart_rate = heart_rate
    vital.respiratory_rate = respiratory_rate
    vital.body_temperature = body_temperature
    vital.spo2 = spo2
    vital.systolic_bp = systolic_bp
    vital.diastolic_bp = diastolic_bp
    vital.age = 45
    vital.gender = "M"
    vital.pulse_pressure = systolic_bp - diastolic_bp
    vital.mean_arterial_pressure = diastolic_bp + (systolic_bp - diastolic_bp) / 3

    return vital


def test_assess_risk_with_normal_vitals():
    """
    test that normal vitals result in low risk.

    verifies:
        - risk_level is "low"
        - no signals are generated
        - vitals_summary is computed correctly
    """
    # create 10 vitals with normal values
    vitals = [
        _create_mock_vital(
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "low", "normal vitals should produce low risk"
    assert len(result["signals"]) == 0, "normal vitals should have no signals"
    assert "heart_rate_avg" in result["vitals_summary"], "summary should include hr avg"
    assert result["vitals_summary"]["heart_rate_avg"] == 75.0


def test_assess_risk_with_empty_vitals():
    """
    test that empty vitals list returns low risk with no signals.

    verifies:
        - handles empty list gracefully
        - returns low risk by default
    """
    result = assess_risk([])

    assert result["risk_level"] == "low"
    assert result["signals"] == []
    assert result["vitals_summary"] == {}


def test_assess_risk_with_extreme_tachycardia():
    """
    test that extreme high heart rate triggers high risk.

    verifies:
        - risk_level is "high"
        - appropriate signal is generated
    """
    # create vitals with sustained tachycardia (>120 bpm)
    vitals = [
        _create_mock_vital(
            heart_rate=135.0,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "extreme tachycardia should be high risk"
    assert len(result["signals"]) > 0, "should generate at least one signal"
    assert any("elevated heart rate" in s.lower() for s in result["signals"])


def test_assess_risk_with_mild_tachycardia():
    """
    test that mild high heart rate triggers moderate risk.

    verifies:
        - risk_level is "moderate"
        - appropriate signal is generated
    """
    # create vitals with mild tachycardia (100-120 bpm)
    vitals = [
        _create_mock_vital(
            heart_rate=110.0,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "moderate", "mild tachycardia should be moderate risk"
    assert len(result["signals"]) > 0
    assert any("heart rate" in s.lower() for s in result["signals"])


def test_assess_risk_with_extreme_hypoxia():
    """
    test that low oxygen saturation triggers high risk.

    verifies:
        - risk_level is "high"
        - hypoxia signal is generated
    """
    # create vitals with severe hypoxia (<92%)
    vitals = [
        _create_mock_vital(
            spo2=88.0,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "severe hypoxia should be high risk"
    assert any("oxygen saturation" in s.lower() for s in result["signals"])


def test_assess_risk_with_mild_hypoxia():
    """
    test that mildly low oxygen saturation triggers moderate risk.

    verifies:
        - risk_level is "moderate"
        - hypoxia signal is generated
    """
    # create vitals with mild hypoxia (92-95%)
    vitals = [
        _create_mock_vital(
            spo2=93.5,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "moderate", "mild hypoxia should be moderate risk"
    assert any("oxygen saturation" in s.lower() for s in result["signals"])


def test_assess_risk_with_extreme_hypertension():
    """
    test that extremely high blood pressure triggers high risk.

    verifies:
        - risk_level is "high"
        - hypertension signal is generated
    """
    # create vitals with severe hypertension (>160 systolic)
    vitals = [
        _create_mock_vital(
            systolic_bp=175,
            diastolic_bp=95,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "severe hypertension should be high risk"
    assert any("blood pressure" in s.lower() for s in result["signals"])


def test_assess_risk_with_extreme_hypotension():
    """
    test that extremely low blood pressure triggers high risk.

    verifies:
        - risk_level is "high"
        - hypotension signal is generated
    """
    # create vitals with severe hypotension (<85 systolic)
    vitals = [
        _create_mock_vital(
            systolic_bp=78,
            diastolic_bp=48,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "severe hypotension should be high risk"
    assert any("blood pressure" in s.lower() for s in result["signals"])


def test_assess_risk_with_extreme_fever():
    """
    test that high fever triggers high risk.

    verifies:
        - risk_level is "high"
        - fever signal is generated
    """
    # create vitals with high fever (>38°c)
    vitals = [
        _create_mock_vital(
            body_temperature=38.8,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "high fever should be high risk"
    assert any("temperature" in s.lower() for s in result["signals"])


def test_assess_risk_with_extreme_tachypnea():
    """
    test that very high respiratory rate triggers high risk.

    verifies:
        - risk_level is "high"
        - tachypnea signal is generated
    """
    # create vitals with severe tachypnea (>24 breaths/min)
    vitals = [
        _create_mock_vital(
            respiratory_rate=28.0,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "high", "severe tachypnea should be high risk"
    assert any("respiratory rate" in s.lower() for s in result["signals"])


def test_assess_risk_with_multiple_mild_abnormalities():
    """
    test that multiple mild abnormalities still result in moderate risk.

    verifies:
        - risk_level is "moderate" (not escalated to high)
        - multiple signals are generated
    """
    # create vitals with mild tachycardia + mild hypoxia
    vitals = [
        _create_mock_vital(
            heart_rate=110.0,
            spo2=93.5,
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    result = assess_risk(vitals)

    assert result["risk_level"] == "moderate", "multiple mild abnormalities should be moderate"
    assert len(result["signals"]) >= 2, "should have signals for both hr and spo2"


def test_check_sustained_condition_with_sustained_high():
    """
    test sustained condition detection for values above threshold.

    verifies:
        - correctly identifies sustained high values
        - calculates percentage exceeding threshold
    """
    # 8 out of 10 values above threshold, avg also above
    values = [105.0, 110.0, 108.0, 112.0, 109.0, 111.0, 107.0, 110.0, 95.0, 98.0]
    is_sustained, pct = _check_sustained_condition(values, 100, "greater")

    assert is_sustained is True, "should detect sustained high condition"
    assert pct == 0.8, "80% of values exceed threshold"


def test_check_sustained_condition_with_non_sustained():
    """
    test sustained condition detection with insufficient percentage.

    verifies:
        - correctly rejects non-sustained conditions
    """
    # only 3 out of 10 values above threshold (30% < 40% required)
    values = [105.0, 95.0, 98.0, 92.0, 97.0, 110.0, 93.0, 94.0, 96.0, 108.0]
    is_sustained, pct = _check_sustained_condition(values, 100, "greater")

    assert is_sustained is False, "should not detect sustained condition with <40% exceeding"


def test_check_sustained_condition_with_sustained_low():
    """
    test sustained condition detection for values below threshold.

    verifies:
        - correctly identifies sustained low values
    """
    # 8 out of 10 values below threshold, avg also below
    values = [88.0, 87.0, 89.0, 86.0, 88.5, 87.5, 89.0, 88.0, 95.0, 94.0]
    is_sustained, pct = _check_sustained_condition(values, 92, "less")

    assert is_sustained is True, "should detect sustained low condition"
    assert pct == 0.8


def test_aggregate_risk_level_with_extreme_signal():
    """
    test risk aggregation with extreme severity signal.

    verifies:
        - extreme signal results in high risk
    """
    signals = [
        {"severity": "mild", "description": "test"},
        {"severity": "extreme", "description": "test"}
    ]

    risk = _aggregate_risk_level(signals)
    assert risk == "high", "any extreme signal should result in high risk"


def test_aggregate_risk_level_with_only_mild():
    """
    test risk aggregation with only mild signals.

    verifies:
        - mild signals result in moderate risk
    """
    signals = [
        {"severity": "mild", "description": "test1"},
        {"severity": "mild", "description": "test2"}
    ]

    risk = _aggregate_risk_level(signals)
    assert risk == "moderate", "only mild signals should result in moderate risk"


def test_aggregate_risk_level_with_no_signals():
    """
    test risk aggregation with no signals.

    verifies:
        - no signals result in low risk
    """
    risk = _aggregate_risk_level([])
    assert risk == "low", "no signals should result in low risk"


def test_analyze_heart_rate_returns_none_for_normal():
    """
    test that normal heart rate returns no signal.

    verifies:
        - _analyze_heart_rate returns none for normal values
    """
    vitals = [_create_mock_vital(heart_rate=75.0) for _ in range(10)]
    signal = _analyze_heart_rate(vitals)
    assert signal is None, "normal hr should return no signal"


def test_analyze_spo2_returns_signal_for_low():
    """
    test that low spo2 returns appropriate signal.

    verifies:
        - _analyze_spo2 detects hypoxia
    """
    vitals = [_create_mock_vital(spo2=88.0) for _ in range(10)]
    signal = _analyze_spo2(vitals)
    assert signal is not None, "low spo2 should return signal"
    assert signal["severity"] == "extreme"


def test_analyze_blood_pressure_returns_signal_for_hypertension():
    """
    test that high bp returns appropriate signal.

    verifies:
        - _analyze_blood_pressure detects hypertension
    """
    vitals = [_create_mock_vital(systolic_bp=175, diastolic_bp=95) for _ in range(10)]
    signal = _analyze_blood_pressure(vitals)
    assert signal is not None, "hypertension should return signal"
    assert signal["severity"] == "extreme"


@pytest.fixture(scope="module")
def test_session():
    """
    create a test database session.

    yields:
        sqlalchemy session for testing
    """
    session = get_db_session()
    yield session
    session.close()


def test_assess_risk_with_real_deteriorating_data(test_session):
    """
    test risk assessment using real synthetic deteriorating data.

    verifies:
        - last 2 hours of deteriorating vitals show elevated risk
        - risk level is moderate or high
        - signals are generated
    """
    repo = VitalsRepository(test_session)

    # get last 2 hours of vitals (should show deterioration)
    recent_vitals = repo.get_recent_vitals("PATIENT_001", window_hours=2)

    # ensure we have data
    assert len(recent_vitals) > 0, "should have vitals in database"

    # assess risk
    result = assess_risk(recent_vitals)

    # with deteriorating trend, we expect at least moderate risk
    assert result["risk_level"] in ["moderate", "high"], \
        f"deteriorating vitals should show elevated risk, got {result['risk_level']}"

    # should have at least one signal
    assert len(result["signals"]) > 0, "deteriorating vitals should generate signals"

    print(f"\nrisk assessment on real data:")
    print(f"  risk level: {result['risk_level']}")
    print(f"  signals ({len(result['signals'])}):")
    for signal in result["signals"]:
        print(f"    - {signal}")
    print(f"  vitals summary:")
    for key, value in result["vitals_summary"].items():
        print(f"    {key}: {value:.1f}")
