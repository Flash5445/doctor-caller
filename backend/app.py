"""
flask rest api for ai doctor call agent.

provides endpoints for:
- retrieving patient vitals
- orchestrating doctor call workflow
- checking call status
"""

from flask import Flask, request, jsonify
from datetime import datetime
import os

from backend.config import get_db_session
from backend.repositories.vitals_repository import VitalsRepository
from backend.services.risk_engine import assess_risk
from backend.services.summary_service import (
    generate_vitals_summary,
    InvalidInputError,
    APIError,
    ValidationError
)
from backend.services.call_service import TwilioCallService
from twilio.twiml.voice_response import VoiceResponse


# initialize flask app
app = Flask(__name__)

# initialize call service (real twilio integration)
try:
    call_service = TwilioCallService()
except ValueError as e:
    # fallback to stub if twilio env vars not set (for testing)
    print(f"warning: twilio not configured ({e}), using stub")
    from backend.services.call_service_stub import CallServiceStub
    call_service = CallServiceStub()


def error_response(message: str, status_code: int) -> tuple:
    """
    create standardized error response.

    args:
        message: error message
        status_code: http status code

    returns:
        tuple of (json_response, status_code)
    """
    return jsonify({
        "success": False,
        "error": message,
        "status_code": status_code
    }), status_code


@app.route('/health', methods=['GET'])
def health():
    """
    health check endpoint.

    returns:
        json response with health status
    """
    return jsonify({
        "status": "healthy",
        "service": "ai-doctor-call-agent",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


@app.route('/patients/<patient_id>/vitals/recent', methods=['GET'])
def get_recent_vitals(patient_id: str):
    """
    retrieve recent vitals for a patient.

    args:
        patient_id: patient identifier from url path

    query parameters:
        hours: time window in hours (default: 2)

    returns:
        json response with vitals data or error
    """
    try:
        # parse query parameters
        hours = request.args.get('hours', default=2, type=int)

        # validate hours parameter
        if hours < 1 or hours > 24:
            return error_response("hours must be between 1 and 24", 400)

        # get database session and repository
        session = get_db_session()
        repo = VitalsRepository(session)

        # fetch vitals
        vitals = repo.get_recent_vitals(patient_id, window_hours=hours)

        if not vitals:
            return error_response(
                f"no vitals found for patient {patient_id} in last {hours} hours",
                404
            )

        # convert vitals to dict format
        vitals_data = [v.to_dict() for v in vitals]

        # build response
        response = {
            "success": True,
            "patient_id": patient_id,
            "time_window_hours": hours,
            "vitals_count": len(vitals_data),
            "vitals": vitals_data
        }

        session.close()
        return jsonify(response), 200

    except Exception as e:
        return error_response(f"internal error: {str(e)}", 500)


@app.route('/call-doctor', methods=['POST'])
def call_doctor():
    """
    orchestrate full workflow: fetch vitals, assess risk, generate summary, initiate call.

    request body:
        {
            "patient_id": "string",
            "hours": 2  // optional, default 2
        }

    returns:
        json response with call details or error
    """
    try:
        # parse request body
        data = request.get_json(silent=True)

        if data is None:
            return error_response("request body is required", 400)

        patient_id = data.get('patient_id')
        if not patient_id:
            return error_response("patient_id is required", 400)

        hours = data.get('hours', 2)

        # validate hours parameter
        if not isinstance(hours, int) or hours < 1 or hours > 24:
            return error_response("hours must be an integer between 1 and 24", 400)

        # step 1: fetch vitals
        session = get_db_session()
        repo = VitalsRepository(session)
        vitals = repo.get_recent_vitals(patient_id, window_hours=hours)

        if not vitals:
            session.close()
            return error_response(
                f"no vitals found for patient {patient_id} in last {hours} hours",
                404
            )

        # step 2: assess risk
        risk_assessment = assess_risk(vitals)

        # step 3: generate summary
        try:
            summary_result = generate_vitals_summary(
                patient_id,
                vitals,
                risk_assessment
            )
            summary_text = summary_result["summary_text"]
        except (InvalidInputError, ValidationError) as e:
            session.close()
            return error_response(f"summary generation failed: {str(e)}", 500)
        except APIError as e:
            session.close()
            return error_response(f"llm api error: {str(e)}", 500)

        # step 4 (placeholder): initiate call using stub service
        call_id = call_service.start_call(summary_text, patient_id)

        session.close()

        # build response
        response = {
            "success": True,
            "message": f"call initiated successfully for patient {patient_id}",
            "call_id": call_id,
            "patient_id": patient_id,
            "risk_level": risk_assessment["risk_level"],
            "summary_preview": summary_text[:150] + "..." if len(summary_text) > 150 else summary_text,
            "vitals_analyzed": len(vitals),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        return jsonify(response), 200

    except Exception as e:
        return error_response(f"internal error: {str(e)}", 500)


@app.route('/calls/<call_id>/status', methods=['GET'])
def get_call_status(call_id: str):
    """
    retrieve call status by call_id.

    args:
        call_id: call identifier from url path

    returns:
        json response with call status or error
    """
    try:
        # fetch call status from service
        call_data = call_service.get_call_status(call_id)

        if not call_data:
            return error_response(f"call {call_id} not found", 404)

        # build response (exclude summary_text for brevity)
        response = {
            "success": True,
            "call_id": call_data["call_id"],
            "status": call_data["status"],
            "patient_id": call_data["patient_id"],
            "created_at": call_data["created_at"],
            "completed_at": call_data.get("completed_at"),
            "duration_seconds": call_data.get("duration_seconds")
        }

        return jsonify(response), 200

    except Exception as e:
        return error_response(f"internal error: {str(e)}", 500)


@app.route('/twilio/voice', methods=['POST'])
def twilio_voice_webhook():
    """
    twilio voice webhook - returns twiml for call content.

    called by twilio when call is answered.
    generates twiml response with disclaimer and vitals summary.

    query parameters:
        call_id: our internal call identifier

    returns:
        twiml xml response
    """
    try:
        # get call_id from query parameters
        call_id = request.args.get('call_id')

        if not call_id:
            # return error twiml if call_id missing
            response = VoiceResponse()
            response.say(
                "Error: missing call identifier.",
                voice='Polly.Joanna'
            )
            return str(response), 200, {'Content-Type': 'text/xml'}

        # fetch summary text for this call
        summary_text = call_service.get_summary_for_call(call_id)

        if not summary_text:
            # return error twiml if call not found
            response = VoiceResponse()
            response.say(
                "Error: call data not found.",
                voice='Polly.Joanna'
            )
            return str(response), 200, {'Content-Type': 'text/xml'}

        # build twiml response
        response = VoiceResponse()

        # disclaimer
        response.say(
            "Hello. This is an automated summary call from the A I Doctor Call Agent system. "
            "This is not a diagnosis or treatment recommendation.",
            voice='Polly.Joanna'
        )
        response.pause(length=1)

        # vitals summary
        response.say(
            summary_text,
            voice='Polly.Joanna'
        )
        response.pause(length=1)

        # closing
        response.say(
            "This concludes the automated vitals summary. Thank you.",
            voice='Polly.Joanna'
        )

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        # return error twiml on exception
        response = VoiceResponse()
        response.say(
            f"An error occurred: {str(e)}",
            voice='Polly.Joanna'
        )
        return str(response), 200, {'Content-Type': 'text/xml'}


@app.route('/twilio/status', methods=['POST'])
def twilio_status_callback():
    """
    twilio status callback webhook.

    receives call status updates from twilio.
    currently just logs the status for debugging.

    returns:
        empty 200 response
    """
    try:
        call_sid = request.form.get('CallSid')
        call_status = request.form.get('CallStatus')

        # log status update (in production, update database)
        print(f"twilio status callback: {call_sid} -> {call_status}")

        return '', 200

    except Exception as e:
        print(f"error in status callback: {e}")
        return '', 200


# development server
if __name__ == '__main__':
    # load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # run flask app
    debug_mode = os.getenv('FLASK_DEBUG', 'True') == 'True'
    port = int(os.getenv('FLASK_PORT', 5000))

    app.run(debug=debug_mode, port=port, host='0.0.0.0')
