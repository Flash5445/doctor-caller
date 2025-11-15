"""
vitals data model for storing patient vital signs.

defines the sqlalchemy orm model for the vitals table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Vital(Base):
    """
    represents a single vital signs reading for a patient at a specific time.

    attributes:
        id: primary key
        patient_id: unique patient identifier
        timestamp: when the vital signs were recorded (utc)
        heart_rate: beats per minute
        respiratory_rate: breaths per minute
        body_temperature: degrees celsius
        spo2: oxygen saturation percentage (0-100)
        systolic_bp: systolic blood pressure (mmhg)
        diastolic_bp: diastolic blood pressure (mmhg)
        age: patient age in years
        gender: patient gender
        pulse_pressure: derived metric (systolic - diastolic)
        mean_arterial_pressure: derived metric (map)
    """

    __tablename__ = "vitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # vital signs
    heart_rate = Column(Float, nullable=False)
    respiratory_rate = Column(Float, nullable=False)
    body_temperature = Column(Float, nullable=False)
    spo2 = Column(Float, nullable=False)
    systolic_bp = Column(Integer, nullable=False)
    diastolic_bp = Column(Integer, nullable=False)

    # demographics (constant per patient)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)

    # derived metrics
    pulse_pressure = Column(Float, nullable=True)
    mean_arterial_pressure = Column(Float, nullable=True)

    def __repr__(self) -> str:
        """string representation of vital record."""
        return (
            f"<Vital(patient_id='{self.patient_id}', "
            f"timestamp='{self.timestamp}', "
            f"hr={self.heart_rate}, "
            f"bp={self.systolic_bp}/{self.diastolic_bp})>"
        )

    def to_dict(self) -> dict:
        """
        convert vital record to dictionary.

        returns:
            dict representation of the vital record
        """
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "heart_rate": self.heart_rate,
            "respiratory_rate": self.respiratory_rate,
            "body_temperature": self.body_temperature,
            "spo2": self.spo2,
            "systolic_bp": self.systolic_bp,
            "diastolic_bp": self.diastolic_bp,
            "age": self.age,
            "gender": self.gender,
            "pulse_pressure": self.pulse_pressure,
            "mean_arterial_pressure": self.mean_arterial_pressure,
        }
