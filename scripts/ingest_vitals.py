"""
synthetic time-series vitals data generator and database ingestion script.

generates realistic deteriorating vitals data for one patient based on a baseline
from the kaggle dataset, then inserts into the database.
"""

import sys
import csv
from datetime import datetime, timedelta
from typing import List, Dict
import random

# add parent directory to path for imports
sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

from backend.models.vitals import Base, Vital
from backend.config import engine, get_db_session


def load_baseline_patient(csv_path: str) -> Dict:
    """
    load baseline patient data from csv (first patient).

    args:
        csv_path: path to vitals.csv file

    returns:
        dict containing baseline patient vital values
    """
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        first_patient = next(reader)

    baseline = {
        "heart_rate": float(first_patient["Heart Rate"]),
        "respiratory_rate": float(first_patient["Respiratory Rate"]),
        "body_temperature": float(first_patient["Body Temperature"]),
        "spo2": float(first_patient["Oxygen Saturation"]),
        "systolic_bp": int(first_patient["Systolic Blood Pressure"]),
        "diastolic_bp": int(first_patient["Diastolic Blood Pressure"]),
        "age": int(first_patient["Age"]),
        "gender": first_patient["Gender"],
    }

    return baseline


def generate_synthetic_timeseries(
    baseline: Dict, num_records: int = 150, patient_id: str = "PATIENT_001"
) -> List[Vital]:
    """
    generate synthetic time-series vitals with deteriorating trend.

    creates realistic vital sign variations using random walk with a gradual
    deterioration trend (increasing hr, decreasing spo2, increasing bp).

    args:
        baseline: dict with initial vital values
        num_records: number of time-series points (default 150 = 2.5 hours)
        patient_id: patient identifier (default "PATIENT_001")

    returns:
        list of vital model instances ready for database insertion
    """
    vitals = []
    current_time = datetime.utcnow() - timedelta(minutes=num_records)

    # initialize current values from baseline
    current_hr = baseline["heart_rate"]
    current_rr = baseline["respiratory_rate"]
    current_temp = baseline["body_temperature"]
    current_spo2 = baseline["spo2"]
    current_systolic = baseline["systolic_bp"]
    current_diastolic = baseline["diastolic_bp"]

    # deterioration trends (small incremental changes per minute)
    hr_trend = 0.15  # heart rate increases over time
    spo2_trend = -0.03  # oxygen saturation decreases
    systolic_trend = 0.08  # blood pressure increases
    temp_trend = 0.002  # temperature increases slightly

    for i in range(num_records):
        # apply random walk with trend
        current_hr += random.gauss(hr_trend, 2.5)
        current_rr += random.gauss(0, 1.0)
        current_temp += random.gauss(temp_trend, 0.15)
        current_spo2 += random.gauss(spo2_trend, 0.5)
        current_systolic += random.gauss(systolic_trend, 3.0)
        current_diastolic += random.gauss(0.02, 2.0)

        # clamp to physiologically realistic bounds
        current_hr = max(45, min(180, current_hr))
        current_rr = max(8, min(30, current_rr))
        current_temp = max(35.0, min(41.0, current_temp))
        current_spo2 = max(70, min(100, current_spo2))
        current_systolic = max(80, min(200, current_systolic))
        current_diastolic = max(50, min(130, current_diastolic))

        # ensure systolic > diastolic
        if current_systolic <= current_diastolic:
            current_systolic = current_diastolic + 20

        # calculate derived metrics
        pulse_pressure = current_systolic - current_diastolic
        mean_arterial_pressure = current_diastolic + (pulse_pressure / 3)

        # create vital record
        vital = Vital(
            patient_id=patient_id,
            timestamp=current_time + timedelta(minutes=i),
            heart_rate=round(current_hr, 1),
            respiratory_rate=round(current_rr, 1),
            body_temperature=round(current_temp, 2),
            spo2=round(current_spo2, 2),
            systolic_bp=int(round(current_systolic)),
            diastolic_bp=int(round(current_diastolic)),
            age=baseline["age"],
            gender=baseline["gender"],
            pulse_pressure=round(pulse_pressure, 2),
            mean_arterial_pressure=round(mean_arterial_pressure, 2),
        )

        vitals.append(vital)

    return vitals


def ingest_vitals(csv_path: str, num_records: int = 150) -> int:
    """
    main ingestion function: load baseline, generate synthetic data, insert to db.

    args:
        csv_path: path to vitals.csv file
        num_records: number of synthetic records to generate

    returns:
        number of records inserted
    """
    print(f"loading baseline patient from {csv_path}...")
    baseline = load_baseline_patient(csv_path)
    print(f"baseline patient loaded: {baseline}")

    print(f"\ngenerating {num_records} synthetic vital records...")
    vitals = generate_synthetic_timeseries(
        baseline, num_records=num_records, patient_id="PATIENT_001"
    )
    print(f"generated {len(vitals)} records")

    print("\ncreating database tables...")
    Base.metadata.create_all(bind=engine)
    print("tables created")

    print("\ninserting vitals into database...")
    session = get_db_session()
    try:
        session.add_all(vitals)
        session.commit()
        print(f"successfully inserted {len(vitals)} records for PATIENT_001")
        return len(vitals)
    except Exception as e:
        session.rollback()
        print(f"error during insertion: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    csv_path = "/Users/gurnoor/Desktop/doctor-caller/vitals.csv"
    num_inserted = ingest_vitals(csv_path, num_records=150)
    print(f"\ningestion complete! {num_inserted} records in database.")
