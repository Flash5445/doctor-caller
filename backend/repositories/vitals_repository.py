"""
repository for querying patient vitals data.

provides data access methods for retrieving vital signs from the database.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.models.vitals import Vital


class VitalsRepository:
    """
    data access layer for patient vitals.

    handles all database queries related to vital signs.
    """

    def __init__(self, db_session: Session):
        """
        initialize repository with database session.

        args:
            db_session: sqlalchemy session for database operations
        """
        self.session = db_session

    def get_recent_vitals(
        self, patient_id: str, window_hours: int = 2
    ) -> List[Vital]:
        """
        fetch vitals for the last n hours for a specific patient.

        args:
            patient_id: unique patient identifier
            window_hours: time window in hours (default 2)

        returns:
            list of vital records, ordered by timestamp ascending (oldest first)
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)

        vitals = (
            self.session.query(Vital)
            .filter(Vital.patient_id == patient_id)
            .filter(Vital.timestamp >= cutoff_time)
            .order_by(Vital.timestamp.asc())
            .all()
        )

        return vitals

    def get_latest_vitals(self, patient_id: str) -> Optional[Vital]:
        """
        fetch the most recent vital reading for a patient.

        args:
            patient_id: unique patient identifier

        returns:
            single vital record (most recent) or none if no data exists
        """
        latest = (
            self.session.query(Vital)
            .filter(Vital.patient_id == patient_id)
            .order_by(Vital.timestamp.desc())
            .first()
        )

        return latest

    def get_all_vitals(self, patient_id: str) -> List[Vital]:
        """
        fetch all vital records for a patient.

        args:
            patient_id: unique patient identifier

        returns:
            list of all vital records for the patient, ordered by timestamp ascending
        """
        vitals = (
            self.session.query(Vital)
            .filter(Vital.patient_id == patient_id)
            .order_by(Vital.timestamp.asc())
            .all()
        )

        return vitals

    def count_vitals(self, patient_id: str) -> int:
        """
        count total number of vital records for a patient.

        args:
            patient_id: unique patient identifier

        returns:
            number of vital records
        """
        count = (
            self.session.query(Vital).filter(Vital.patient_id == patient_id).count()
        )

        return count
