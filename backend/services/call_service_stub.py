"""
stub call service for testing api endpoints.

temporary implementation that mocks twilio call functionality.
will be replaced with real twilio integration in step 5.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional


class CallServiceStub:
    """
    stub implementation of call service for testing.

    provides in-memory storage and mock call functionality.
    does not make actual phone calls - simulates successful completion.
    """

    def __init__(self):
        """initialize stub with empty call storage."""
        self.calls: Dict[str, dict] = {}

    def start_call(self, summary_text: str, patient_id: str) -> str:
        """
        initiate a mock phone call.

        simulates successful call initiation and immediate completion.
        stores call data in memory for status retrieval.

        args:
            summary_text: summary to be delivered via call
            patient_id: patient identifier

        returns:
            call_id: unique identifier for this call
        """
        # generate unique call id
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # create mock call record
        created_at = datetime.utcnow()
        self.calls[call_id] = {
            "call_id": call_id,
            "status": "completed",  # mock as immediately completed
            "patient_id": patient_id,
            "summary_text": summary_text,
            "created_at": created_at.isoformat() + "Z",
            "completed_at": (created_at + timedelta(seconds=120)).isoformat() + "Z",
            "duration_seconds": 120
        }

        return call_id

    def get_call_status(self, call_id: str) -> Optional[dict]:
        """
        retrieve call status by call_id.

        args:
            call_id: unique call identifier

        returns:
            dict with call details or none if not found
        """
        return self.calls.get(call_id)

    def clear_calls(self):
        """
        clear all stored calls.

        useful for testing cleanup.
        """
        self.calls.clear()
