"""
twilio call service for initiating outbound doctor calls.

implements real twilio programmable voice integration to deliver
vitals summaries to medical providers via phone.
"""

import os
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, Optional
from twilio.rest import Client  # type: ignore
from twilio.base.exceptions import TwilioRestException  # type: ignore


class TwilioCallService:
    """
    twilio-based call service for automated doctor calls.

    manages outbound calls using twilio programmable voice api.
    stores call metadata and summary text for webhook delivery.
    """

    def __init__(self) -> None:
        """
        initialize twilio client and call storage.

        reads twilio credentials from environment variables:
        - TWILIO_ACCOUNT_SID
        - TWILIO_AUTH_TOKEN
        - TWILIO_CALLER_ID (verified twilio number)
        - PROVIDER_PHONE_NUMBER (target doctor/hospital number)
        - WEBHOOK_BASE_URL (public url for twilio webhooks)
        """
        # load twilio credentials
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.caller_id = os.getenv('TWILIO_CALLER_ID')
        self.provider_number = os.getenv('PROVIDER_PHONE_NUMBER')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')

        # validate required env vars
        if not all([self.account_sid, self.auth_token, self.caller_id, self.provider_number]):
            raise ValueError(
                "missing required environment variables: "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALLER_ID, PROVIDER_PHONE_NUMBER"
            )

        # initialize twilio client
        self.client = Client(self.account_sid, self.auth_token)

        # in-memory call storage (for mvp)
        # in production, this should be a database
        self.calls: Dict[str, Dict[str, Any]] = {}

    def start_call(self, summary_text: str, patient_id: str) -> str:
        """
        initiate outbound call via twilio.

        creates a call to PROVIDER_PHONE_NUMBER that delivers the vitals summary
        via text-to-speech when answered.

        args:
            summary_text: vitals summary to be delivered via tts
            patient_id: patient identifier

        returns:
            call_id: unique identifier for this call

        raises:
            TwilioRestException: if twilio api call fails
            ValueError: if required env vars not set
        """
        # generate unique call id
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # construct webhook url with call_id parameter
        webhook_url = f"{self.webhook_base_url}/twilio/voice?call_id={call_id}"

        try:
            # initiate call via twilio
            call = self.client.calls.create(
                to=self.provider_number,
                from_=self.caller_id,
                url=webhook_url,
                method='POST',
                status_callback=f"{self.webhook_base_url}/twilio/status",
                status_callback_event=['completed'],
                status_callback_method='POST'
            )

            # store call metadata
            self.calls[call_id] = {
                "call_id": call_id,
                "call_sid": call.sid,
                "patient_id": patient_id,
                "summary_text": summary_text,
                "status": self._map_twilio_status(call.status),
                "to": self.provider_number,
                "from": self.caller_id,
                "created_at": datetime.now(UTC).isoformat(),
                "completed_at": None,
                "duration_seconds": None
            }

            return call_id

        except TwilioRestException as e:
            # re-raise the exception with additional context in the message
            raise TwilioRestException(
                status=e.status,
                uri=e.uri,
                msg=f"twilio api error: {e.msg}",
                code=e.code
            )

    def get_call_status(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        retrieve call status by call_id.

        fetches stored call data and optionally queries twilio for latest status.

        args:
            call_id: unique call identifier

        returns:
            dict with call details or none if not found
        """
        if call_id not in self.calls:
            return None

        call_data = self.calls[call_id]

        # optionally query twilio for latest status
        # (useful for calls in progress)
        try:
            call_sid = call_data["call_sid"]
            twilio_call = self.client.calls(call_sid).fetch()

            # update status from twilio
            call_data["status"] = self._map_twilio_status(twilio_call.status)

            # update duration if completed
            if twilio_call.duration:
                call_data["duration_seconds"] = int(twilio_call.duration)

            # update completion time if completed
            if twilio_call.status in ['completed', 'busy', 'no-answer', 'failed', 'canceled']:
                if not call_data["completed_at"]:
                    call_data["completed_at"] = datetime.now(UTC).isoformat()

        except TwilioRestException:
            # if twilio query fails, return stored data
            pass

        # return call data (exclude summary_text for brevity)
        return {
            "call_id": call_data["call_id"],
            "call_sid": call_data["call_sid"],
            "status": call_data["status"],
            "patient_id": call_data["patient_id"],
            "to": call_data["to"],
            "from": call_data["from"],
            "created_at": call_data["created_at"],
            "completed_at": call_data["completed_at"],
            "duration_seconds": call_data["duration_seconds"]
        }

    def get_summary_for_call(self, call_id: str) -> Optional[str]:
        """
        retrieve summary text for a call.

        used by webhook endpoint to get summary for twiml generation.

        args:
            call_id: unique call identifier

        returns:
            summary text or none if call not found
        """
        if call_id not in self.calls:
            return None
        summary: str = self.calls[call_id]["summary_text"]
        return summary

    def _map_twilio_status(self, twilio_status: str) -> str:
        """
        map twilio call status to our status.

        args:
            twilio_status: status from twilio api

        returns:
            our standardized status string
        """
        status_map = {
            "queued": "queued",
            "ringing": "initiated",
            "in-progress": "in-progress",
            "completed": "completed",
            "busy": "failed",
            "no-answer": "failed",
            "failed": "failed",
            "canceled": "failed"
        }
        return status_map.get(twilio_status, "unknown")

    def clear_calls(self) -> None:
        """
        clear all stored calls.

        useful for testing cleanup.
        """
        self.calls.clear()
