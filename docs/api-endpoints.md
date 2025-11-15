# api endpoints documentation

## overview

rest api for the ai doctor call agent system. provides endpoints for retrieving patient vitals, orchestrating doctor call workflows, and checking call status.

**base url (development):** `http://localhost:5000`

**technology:** flask 3.0.0

---

## authentication

**mvp:** no authentication required

**future:** will implement api key authentication and/or oauth2 for production deployments.

---

## endpoints

### health check

#### GET /health

health check endpoint to verify api is running.

**request:**
```http
GET /health HTTP/1.1
Host: localhost:5000
```

**response (200 ok):**
```json
{
  "status": "healthy",
  "service": "ai-doctor-call-agent",
  "timestamp": "2025-11-14T17:30:00Z"
}
```

**use case:** monitoring, load balancer health checks

---

### get recent vitals

#### GET /patients/{patient_id}/vitals/recent

retrieve recent vital signs for a patient.

**path parameters:**
- `patient_id` (string, required): patient identifier

**query parameters:**
- `hours` (integer, optional, default=2): time window in hours (1-24)

**request:**
```http
GET /patients/PATIENT_001/vitals/recent?hours=2 HTTP/1.1
Host: localhost:5000
```

**response (200 ok):**
```json
{
  "success": true,
  "patient_id": "PATIENT_001",
  "time_window_hours": 2,
  "vitals_count": 120,
  "vitals": [
    {
      "id": 1,
      "patient_id": "PATIENT_001",
      "timestamp": "2025-11-14T15:30:00",
      "heart_rate": 75.0,
      "respiratory_rate": 16.0,
      "body_temperature": 36.8,
      "spo2": 98.0,
      "systolic_bp": 120,
      "diastolic_bp": 80,
      "age": 45,
      "gender": "M",
      "pulse_pressure": 40.0,
      "mean_arterial_pressure": 93.33
    },
    // ... more vitals
  ]
}
```

**error responses:**

**400 bad request** - invalid hours parameter:
```json
{
  "success": false,
  "error": "hours must be between 1 and 24",
  "status_code": 400
}
```

**404 not found** - patient not found or no vitals in time window:
```json
{
  "success": false,
  "error": "no vitals found for patient PATIENT_001 in last 2 hours",
  "status_code": 404
}
```

**500 internal server error** - unexpected error:
```json
{
  "success": false,
  "error": "internal error: [details]",
  "status_code": 500
}
```

---

### call doctor

#### POST /call-doctor

orchestrate full workflow: fetch vitals, assess risk, generate summary, initiate call.

**workflow:**
1. fetch last n hours of vitals (step 1)
2. assess risk level (step 2)
3. generate ai summary (step 3)
4. initiate phone call via twilio (step 5)

**request:**
```http
POST /call-doctor HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "patient_id": "PATIENT_001",
  "hours": 2
}
```

**request body:**
- `patient_id` (string, required): patient identifier
- `hours` (integer, optional, default=2): time window in hours (1-24)

**response (200 ok):**
```json
{
  "success": true,
  "message": "call initiated successfully for patient PATIENT_001",
  "call_id": "call_a1b2c3d4",
  "patient_id": "PATIENT_001",
  "risk_level": "moderate",
  "summary_preview": "Patient PATIENT_001 vital signs from 15:30 to 17:30 show stable measurements over the two hour monitoring period. Heart rate averaged 72 bpm...",
  "vitals_analyzed": 120,
  "timestamp": "2025-11-14T17:30:00Z"
}
```

**response fields:**
- `call_id`: unique identifier for this call (use with /calls/{call_id}/status)
- `risk_level`: "low", "moderate", or "high"
- `summary_preview`: first 150 characters of generated summary
- `vitals_analyzed`: number of vital records processed

**error responses:**

**400 bad request** - missing patient_id:
```json
{
  "success": false,
  "error": "patient_id is required",
  "status_code": 400
}
```

**400 bad request** - invalid hours parameter:
```json
{
  "success": false,
  "error": "hours must be an integer between 1 and 24",
  "status_code": 400
}
```

**400 bad request** - missing request body:
```json
{
  "success": false,
  "error": "request body is required",
  "status_code": 400
}
```

**404 not found** - patient not found or no vitals:
```json
{
  "success": false,
  "error": "no vitals found for patient PATIENT_001 in last 2 hours",
  "status_code": 404
}
```

**500 internal server error** - summary generation failed:
```json
{
  "success": false,
  "error": "summary generation failed: [details]",
  "status_code": 500
}
```

**500 internal server error** - llm api error:
```json
{
  "success": false,
  "error": "llm api error: [details]",
  "status_code": 500
}
```

---

### get call status

#### GET /calls/{call_id}/status

retrieve status of a call by call_id.

**path parameters:**
- `call_id` (string, required): call identifier (returned from POST /call-doctor)

**request:**
```http
GET /calls/call_a1b2c3d4/status HTTP/1.1
Host: localhost:5000
```

**response (200 ok):**
```json
{
  "success": true,
  "call_id": "call_a1b2c3d4",
  "status": "completed",
  "patient_id": "PATIENT_001",
  "created_at": "2025-11-14T17:30:00Z",
  "completed_at": "2025-11-14T17:32:15Z",
  "duration_seconds": 135
}
```

**status values:**
- `queued`: call queued in twilio but not yet initiated
- `initiated`: call initiated, phone is ringing
- `in-progress`: call answered, currently in progress
- `completed`: call successfully completed
- `failed`: call failed (busy, no answer, error, canceled)
- `unknown`: status could not be determined

**error responses:**

**404 not found** - call_id not found:
```json
{
  "success": false,
  "error": "call call_abc123 not found",
  "status_code": 404
}
```

---

### twilio voice webhook

#### POST /twilio/voice

twilio webhook endpoint for call content delivery.

**description:** called by twilio when an outbound call is answered. generates twiml response with disclaimer and vitals summary using text-to-speech.

**query parameters:**
- `call_id` (string, required): internal call identifier

**request:** initiated by twilio, contains form data with call information

**response (200 ok):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">Hello. This is an automated summary call from the A I Doctor Call Agent system. This is not a diagnosis or treatment recommendation.</Say>
  <Pause length="1"/>
  <Say voice="Polly.Joanna">[vitals summary text]</Say>
  <Pause length="1"/>
  <Say voice="Polly.Joanna">This concludes the automated vitals summary. Thank you.</Say>
</Response>
```

**error response:** returns twiml with error message if call_id missing or invalid

**note:** this endpoint is called by twilio servers, not directly by clients

---

### twilio status callback

#### POST /twilio/status

twilio webhook endpoint for call status updates.

**description:** receives call status updates from twilio as calls progress through their lifecycle.

**request:** initiated by twilio, contains form data with:
- `CallSid`: twilio call identifier
- `CallStatus`: current call status (queued, ringing, in-progress, completed, etc.)

**response (200 ok):**
```
empty response body
```

**note:** this endpoint is called by twilio servers, not directly by clients. currently logs status for debugging; production version should update database.

---

## error handling

### standardized error response

all endpoints return errors in consistent format:

```json
{
  "success": false,
  "error": "human-readable error message",
  "status_code": 400
}
```

### http status codes

- `200 ok`: successful request
- `400 bad request`: invalid input, missing required fields
- `404 not found`: resource not found (patient, call, vitals)
- `500 internal server error`: unexpected server error, api failures

---

## usage examples

### python (requests library)

```python
import requests

base_url = "http://localhost:5000"

# 1. fetch recent vitals
response = requests.get(f"{base_url}/patients/PATIENT_001/vitals/recent?hours=2")
vitals_data = response.json()
print(f"found {vitals_data['vitals_count']} vitals")

# 2. initiate doctor call
call_request = {
    "patient_id": "PATIENT_001",
    "hours": 2
}
response = requests.post(f"{base_url}/call-doctor", json=call_request)
call_data = response.json()
call_id = call_data['call_id']
print(f"call initiated: {call_id}")
print(f"risk level: {call_data['risk_level']}")

# 3. check call status
response = requests.get(f"{base_url}/calls/{call_id}/status")
status_data = response.json()
print(f"call status: {status_data['status']}")
```

### curl

```bash
# health check
curl http://localhost:5000/health

# get recent vitals
curl "http://localhost:5000/patients/PATIENT_001/vitals/recent?hours=2"

# initiate doctor call
curl -X POST http://localhost:5000/call-doctor \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "PATIENT_001", "hours": 2}'

# check call status
curl http://localhost:5000/calls/call_a1b2c3d4/status
```

### javascript (fetch api)

```javascript
const baseUrl = 'http://localhost:5000';

// fetch recent vitals
const vitalsResponse = await fetch(
  `${baseUrl}/patients/PATIENT_001/vitals/recent?hours=2`
);
const vitalsData = await vitalsResponse.json();

// initiate doctor call
const callResponse = await fetch(`${baseUrl}/call-doctor`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ patient_id: 'PATIENT_001', hours: 2 })
});
const callData = await callResponse.json();
console.log('call id:', callData.call_id);

// check call status
const statusResponse = await fetch(
  `${baseUrl}/calls/${callData.call_id}/status`
);
const statusData = await statusResponse.json();
console.log('call status:', statusData.status);
```

---

## testing

### test files

1. `tests/test_api_endpoints.py` - api endpoint tests (16 tests)
2. `tests/test_call_service.py` - twilio call service tests (19 tests)

### api endpoint tests (16 tests)

1. health endpoint returns healthy status
2. get vitals success with default hours
3. get vitals success with custom hours
4. get vitals invalid hours (too low)
5. get vitals invalid hours (too high)
6. get vitals patient not found
7. call doctor success with normal vitals
8. call doctor success with custom hours
9. call doctor missing patient_id
10. call doctor invalid request body
11. call doctor patient not found
12. call doctor invalid hours parameter
13. get call status success
14. get call status not found
15. full workflow end-to-end
16. vitals data format validation

### call service tests (19 tests)

1. initialization with valid env vars
2. initialization with missing env vars
3. initialization with default webhook url
4. start_call success
5. start_call with twilio api error
6. get_call_status for existing call
7. get_call_status for non-existent call
8. get_call_status with twilio fetch error
9. get_summary_for_call success
10. get_summary_for_call non-existent
11. status mapping: queued
12. status mapping: ringing → initiated
13. status mapping: in-progress
14. status mapping: completed
15. status mapping: failed statuses
16. status mapping: unknown
17. clear_calls
18. multiple calls get unique ids
19. call status updates from twilio

### running tests

```bash
# run all tests
.venv/bin/pytest tests/ -v

# run api tests only
.venv/bin/pytest tests/test_api_endpoints.py -v

# run call service tests only
.venv/bin/pytest tests/test_call_service.py -v
```

**expected result:** 35 tests passed (16 api + 19 call service)

---

## implementation details

### file locations

- **main app:** `backend/app.py`
- **twilio call service:** `backend/services/call_service.py`
- **stub call service:** `backend/services/call_service_stub.py`
- **api tests:** `tests/test_api_endpoints.py`
- **call service tests:** `tests/test_call_service.py`

### dependencies

**internal:**
- `backend.config` - database configuration
- `backend.repositories.vitals_repository` - data access (step 1)
- `backend.services.risk_engine` - risk assessment (step 2)
- `backend.services.summary_service` - ai summarization (step 3)
- `backend.services.call_service` - twilio call service (step 5)
- `backend.services.call_service_stub` - fallback stub service (used if twilio not configured)

**external:**
- flask - web framework
- sqlalchemy - database orm
- anthropic - claude api (via summary service)
- twilio - programmable voice api (for phone calls)

### twilio call service

**implementation:** full twilio programmable voice integration (step 5 complete).

**features:**
- initiates real outbound phone calls via twilio api
- delivers vitals summaries using text-to-speech (amazon polly voice)
- tracks call status through twilio callbacks
- stores call metadata in-memory (mvp) or database (production)

**fallback behavior:**
- if twilio environment variables not configured, automatically falls back to stub service
- stub service generates unique call_ids and always returns status="completed"
- allows testing without twilio account

---

## running the api

### development server

```bash
# set environment variables
export FLASK_ENV=development
export FLASK_DEBUG=True
export ANTHROPIC_API_KEY=sk-ant-xxxxx...

# run server
python3 backend/app.py
```

**default:** runs on `http://0.0.0.0:5000`

### local development with twilio

for twilio webhooks to work locally, you need a public url. use ngrok:

```bash
# install ngrok (if not already installed)
brew install ngrok  # macos
# or download from https://ngrok.com

# start your flask app
python3 backend/app.py

# in another terminal, start ngrok
ngrok http 5000

# copy the https url (e.g., https://abc123.ngrok.io)
# set it as WEBHOOK_BASE_URL environment variable
export WEBHOOK_BASE_URL=https://abc123.ngrok.io

# restart flask app with new webhook url
```

**note:** ngrok urls change each time you restart ngrok (unless you have a paid account). you'll need to update `WEBHOOK_BASE_URL` each time.

### environment variables

required:
- `ANTHROPIC_API_KEY` - anthropic claude api key

twilio (optional - falls back to stub if not provided):
- `TWILIO_ACCOUNT_SID` - twilio account sid (starts with AC)
- `TWILIO_AUTH_TOKEN` - twilio authentication token
- `TWILIO_CALLER_ID` - verified twilio phone number (e.g., +15551234567)
- `PROVIDER_PHONE_NUMBER` - target doctor/hospital phone number (e.g., +15559876543)
- `WEBHOOK_BASE_URL` - public url for twilio webhooks (default: http://localhost:5000)
  - for local development: use ngrok (e.g., https://abc123.ngrok.io)
  - for production: use your public domain

optional:
- `FLASK_ENV` - environment (development/production, default: development)
- `FLASK_DEBUG` - debug mode (True/False, default: True)
- `FLASK_PORT` - port number (default: 5000)
- `DATABASE_URL` - database connection string (default: sqlite:///vitals.db)

### production considerations

**not production-ready:** this mvp implementation lacks:
- authentication/authorization
- rate limiting
- cors configuration
- https/ssl
- logging and monitoring
- database connection pooling
- error tracking (sentry, etc.)

---

## future enhancements

### twilio improvements

current implementation delivers one-way automated summaries. future enhancements:
- two-way interactive calls (ivr with speech recognition)
- recording and transcription of calls
- call retry logic for failed calls
- scheduled callback times
- sms notifications as alternative to voice calls
- persistent database storage for call history (currently in-memory)

### authentication

```python
# example with api key authentication
@app.before_request
def authenticate():
    api_key = request.headers.get('X-API-Key')
    if not api_key or not validate_api_key(api_key):
        return error_response("unauthorized", 401)
```

### rate limiting

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/call-doctor', methods=['POST'])
@limiter.limit("10 per minute")
def call_doctor():
    # ...
```

### cors for frontend

```python
from flask_cors import CORS

CORS(app, origins=["http://localhost:3000"])
```

### logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/call-doctor', methods=['POST'])
def call_doctor():
    logger.info(f"call initiated for patient {patient_id}")
    # ...
```

---

## troubleshooting

### common issues

**issue:** "connection refused" when accessing api
**solution:** ensure flask server is running (`python3 backend/app.py`)

**issue:** "no vitals found for patient"
**solution:** run vitals ingestion script: `.venv/bin/python scripts/ingest_vitals.py`

**issue:** "llm api error: authentication failed"
**solution:** verify `ANTHROPIC_API_KEY` environment variable is set correctly

**issue:** "internal error" on /call-doctor
**solution:** check flask logs for details, ensure all dependencies are installed

---

## api versioning

**current:** no versioning (mvp)

**future:** implement versioning in url path:
- `/v1/patients/{id}/vitals/recent`
- `/v1/call-doctor`
- `/v1/calls/{id}/status`

---

## related documentation

- `docs/vitals-ingestion.md` - vitals data layer (step 1)
- `docs/risk-assessment.md` - risk engine (step 2)
- `docs/vitals-summarization.md` - ai summarization (step 3)
- `prd.md` - product requirements document

---

## contact and support

for api issues or questions, consult engineering documentation. this is a development/testing api, not production-ready.
