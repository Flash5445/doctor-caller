"""
tests for vitals repository.

tests data access methods for retrieving vital signs from the database.
"""

import sys
from datetime import datetime, timedelta

sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

import pytest
from backend.models.vitals import Base, Vital
from backend.repositories.vitals_repository import VitalsRepository
from backend.config import engine, get_db_session


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


def test_get_recent_vitals_returns_last_2_hours(test_session):
    """
    test that get_recent_vitals returns only records from last 2 hours.

    verifies:
        - only vitals within the time window are returned
        - results are ordered by timestamp ascending
        - patient_id filtering works correctly
    """
    repo = VitalsRepository(test_session)

    # get vitals from last 2 hours
    recent_vitals = repo.get_recent_vitals("PATIENT_001", window_hours=2)

    assert len(recent_vitals) > 0, "should return at least some vitals"

    # verify all vitals are within last 2 hours
    cutoff = datetime.utcnow() - timedelta(hours=2)
    for vital in recent_vitals:
        assert vital.timestamp >= cutoff, f"vital at {vital.timestamp} is older than 2 hours"
        assert vital.patient_id == "PATIENT_001", "all vitals should belong to PATIENT_001"

    # verify ordering (ascending by timestamp)
    timestamps = [v.timestamp for v in recent_vitals]
    assert timestamps == sorted(timestamps), "vitals should be ordered by timestamp ascending"


def test_get_latest_vitals_returns_most_recent(test_session):
    """
    test that get_latest_vitals returns the most recent vital record.

    verifies:
        - only one record is returned
        - it's the most recent timestamp
    """
    repo = VitalsRepository(test_session)

    latest = repo.get_latest_vitals("PATIENT_001")

    assert latest is not None, "should return a vital record"
    assert latest.patient_id == "PATIENT_001", "should belong to PATIENT_001"

    # verify it's actually the latest by comparing with all vitals
    all_vitals = repo.get_all_vitals("PATIENT_001")
    expected_latest = max(all_vitals, key=lambda v: v.timestamp)

    assert latest.timestamp == expected_latest.timestamp, "should be the most recent vital"


def test_get_all_vitals_returns_all_records(test_session):
    """
    test that get_all_vitals returns all records for a patient.

    verifies:
        - all records are returned
        - results are ordered by timestamp
    """
    repo = VitalsRepository(test_session)

    all_vitals = repo.get_all_vitals("PATIENT_001")

    assert len(all_vitals) == 150, "should return all 150 generated vitals"

    # verify all belong to the patient
    for vital in all_vitals:
        assert vital.patient_id == "PATIENT_001"

    # verify ordering
    timestamps = [v.timestamp for v in all_vitals]
    assert timestamps == sorted(timestamps), "should be ordered by timestamp ascending"


def test_count_vitals_returns_correct_count(test_session):
    """
    test that count_vitals returns the correct number of records.

    verifies:
        - count matches expected number of records
    """
    repo = VitalsRepository(test_session)

    count = repo.count_vitals("PATIENT_001")

    assert count == 150, "should count all 150 generated vitals"


def test_vitals_show_deteriorating_trend(test_session):
    """
    test that generated vitals show a deteriorating trend.

    verifies:
        - heart rate increases over time
        - spo2 decreases over time
        - blood pressure increases over time
    """
    repo = VitalsRepository(test_session)

    all_vitals = repo.get_all_vitals("PATIENT_001")

    # compare first 20% vs last 20% of records
    first_segment = all_vitals[:30]
    last_segment = all_vitals[-30:]

    avg_hr_first = sum(v.heart_rate for v in first_segment) / len(first_segment)
    avg_hr_last = sum(v.heart_rate for v in last_segment) / len(last_segment)

    avg_spo2_first = sum(v.spo2 for v in first_segment) / len(first_segment)
    avg_spo2_last = sum(v.spo2 for v in last_segment) / len(last_segment)

    avg_systolic_first = sum(v.systolic_bp for v in first_segment) / len(first_segment)
    avg_systolic_last = sum(v.systolic_bp for v in last_segment) / len(last_segment)

    # deterioration checks
    assert avg_hr_last > avg_hr_first, "heart rate should increase (deteriorate)"
    assert avg_spo2_last < avg_spo2_first, "spo2 should decrease (deteriorate)"
    assert avg_systolic_last > avg_systolic_first, "blood pressure should increase (deteriorate)"

    print(f"\ndeterioration verified:")
    print(f"  hr: {avg_hr_first:.1f} -> {avg_hr_last:.1f} (+{avg_hr_last - avg_hr_first:.1f})")
    print(f"  spo2: {avg_spo2_first:.1f} -> {avg_spo2_last:.1f} ({avg_spo2_last - avg_spo2_first:.1f})")
    print(f"  bp: {avg_systolic_first:.1f} -> {avg_systolic_last:.1f} (+{avg_systolic_last - avg_systolic_first:.1f})")


def test_vital_to_dict_method(test_session):
    """
    test that vital.to_dict() returns proper dictionary representation.

    verifies:
        - all fields are present
        - timestamp is converted to iso format
    """
    repo = VitalsRepository(test_session)

    vital = repo.get_latest_vitals("PATIENT_001")
    vital_dict = vital.to_dict()

    # verify all expected keys are present
    expected_keys = [
        "id", "patient_id", "timestamp", "heart_rate", "respiratory_rate",
        "body_temperature", "spo2", "systolic_bp", "diastolic_bp",
        "age", "gender", "pulse_pressure", "mean_arterial_pressure"
    ]

    for key in expected_keys:
        assert key in vital_dict, f"key '{key}' should be in dict"

    # verify timestamp is iso format string
    assert isinstance(vital_dict["timestamp"], str), "timestamp should be converted to string"
