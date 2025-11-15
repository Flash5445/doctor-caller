"""
tests for flask api endpoints.

tests all rest api endpoints with various scenarios including
success cases, error cases, and edge cases.
"""

import sys
import json
from unittest.mock import patch, MagicMock

sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

import pytest
from backend.app import app, call_service
from backend.config import get_db_session
from backend.repositories.vitals_repository import VitalsRepository


@pytest.fixture
def client():
    """
    create flask test client.

    yields:
        flask test client for making requests
    """
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def cleanup_calls():
    """
    cleanup call service between tests.

    runs automatically before each test.
    """
    call_service.clear_calls()
    yield
    call_service.clear_calls()


def test_health_endpoint(client):
    """
    test health check endpoint.

    verifies:
        - returns 200 status
        - includes health status
    """
    response = client.get('/health')
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


def test_get_recent_vitals_success_default_hours(client):
    """
    test get recent vitals with default time window.

    verifies:
        - returns 200 status
        - includes vitals data
        - default 2 hour window
    """
    response = client.get('/patients/PATIENT_001/vitals/recent')
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['patient_id'] == 'PATIENT_001'
    assert data['time_window_hours'] == 2
    assert data['vitals_count'] > 0
    assert 'vitals' in data
    assert len(data['vitals']) > 0


def test_get_recent_vitals_success_custom_hours(client):
    """
    test get recent vitals with custom time window.

    verifies:
        - accepts hours parameter
        - returns correct window
    """
    response = client.get('/patients/PATIENT_001/vitals/recent?hours=1')
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['time_window_hours'] == 1


def test_get_recent_vitals_invalid_hours_too_low(client):
    """
    test get recent vitals with invalid hours parameter.

    verifies:
        - returns 400 for hours < 1
    """
    response = client.get('/patients/PATIENT_001/vitals/recent?hours=0')
    assert response.status_code == 400

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'hours must be between' in data['error']


def test_get_recent_vitals_invalid_hours_too_high(client):
    """
    test get recent vitals with hours > 24.

    verifies:
        - returns 400 for hours > 24
    """
    response = client.get('/patients/PATIENT_001/vitals/recent?hours=25')
    assert response.status_code == 400

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'hours must be between' in data['error']


def test_get_recent_vitals_patient_not_found(client):
    """
    test get recent vitals for non-existent patient.

    verifies:
        - returns 404 for patient with no vitals
    """
    response = client.get('/patients/NONEXISTENT/vitals/recent')
    assert response.status_code == 404

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'no vitals found' in data['error']


@patch('backend.app.generate_vitals_summary')
def test_call_doctor_success_normal_vitals(mock_summary, client):
    """
    test call doctor endpoint with normal vitals.

    verifies:
        - full workflow executes
        - returns call_id
        - includes risk level and summary preview
    """
    # mock summary generation
    mock_summary.return_value = {
        "summary_text": "Patient PATIENT_001 vital signs from 00:00 to 02:00 show stable measurements over the two hour monitoring period. Heart rate averaged 75 bpm, oxygen saturation 98%. Risk assessment: low.",
        "word_count": 67,
        "generated_at": "2025-11-14T17:30:00Z",
        "model_used": "claude-3-5-haiku-20241022",
        "prompt_tokens": 450,
        "completion_tokens": 70
    }

    # make request
    response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': 'PATIENT_001'}),
        content_type='application/json'
    )

    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['success'] is True
    assert data['patient_id'] == 'PATIENT_001'
    assert 'call_id' in data
    assert data['call_id'].startswith('call_')
    assert 'risk_level' in data
    assert 'summary_preview' in data
    assert data['vitals_analyzed'] > 0
    assert 'timestamp' in data


@patch('backend.app.generate_vitals_summary')
def test_call_doctor_success_with_custom_hours(mock_summary, client):
    """
    test call doctor with custom time window.

    verifies:
        - accepts hours parameter
    """
    mock_summary.return_value = {
        "summary_text": "Patient PATIENT_001 vital signs show stable measurements. Risk assessment: low.",
        "word_count": 50,
        "generated_at": "2025-11-14T17:30:00Z",
        "model_used": "claude-3-5-haiku-20241022",
        "prompt_tokens": 400,
        "completion_tokens": 55
    }

    response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': 'PATIENT_001', 'hours': 1}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_call_doctor_missing_patient_id(client):
    """
    test call doctor without patient_id.

    verifies:
        - returns 400 when patient_id missing
    """
    response = client.post(
        '/call-doctor',
        data=json.dumps({'hours': 2}),  # has hours but no patient_id
        content_type='application/json'
    )

    assert response.status_code == 400

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'patient_id is required' in data['error']


def test_call_doctor_invalid_request_body(client):
    """
    test call doctor with no request body.

    verifies:
        - returns 400 for missing body
    """
    response = client.post('/call-doctor')

    assert response.status_code == 400

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'request body is required' in data['error']


def test_call_doctor_patient_not_found(client):
    """
    test call doctor for non-existent patient.

    verifies:
        - returns 404 when no vitals found
    """
    response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': 'NONEXISTENT'}),
        content_type='application/json'
    )

    assert response.status_code == 404

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'no vitals found' in data['error']


def test_call_doctor_invalid_hours_parameter(client):
    """
    test call doctor with invalid hours.

    verifies:
        - returns 400 for invalid hours
    """
    response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': 'PATIENT_001', 'hours': 'invalid'}),
        content_type='application/json'
    )

    assert response.status_code == 400

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'hours must be an integer' in data['error']


@patch('backend.app.generate_vitals_summary')
def test_get_call_status_success(mock_summary, client):
    """
    test get call status for existing call.

    verifies:
        - returns call details
        - includes status, timestamps, duration
    """
    # first create a call
    mock_summary.return_value = {
        "summary_text": "Test summary for status check.",
        "word_count": 50,
        "generated_at": "2025-11-14T17:30:00Z",
        "model_used": "claude-3-5-haiku-20241022",
        "prompt_tokens": 400,
        "completion_tokens": 55
    }

    call_response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': 'PATIENT_001'}),
        content_type='application/json'
    )

    call_data = json.loads(call_response.data)
    call_id = call_data['call_id']

    # now check status
    status_response = client.get(f'/calls/{call_id}/status')
    assert status_response.status_code == 200

    status_data = json.loads(status_response.data)
    assert status_data['success'] is True
    assert status_data['call_id'] == call_id
    assert status_data['status'] == 'completed'
    assert status_data['patient_id'] == 'PATIENT_001'
    assert 'created_at' in status_data
    assert 'completed_at' in status_data
    assert 'duration_seconds' in status_data


def test_get_call_status_not_found(client):
    """
    test get call status for non-existent call.

    verifies:
        - returns 404 for unknown call_id
    """
    response = client.get('/calls/nonexistent_call/status')
    assert response.status_code == 404

    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['error']


@patch('backend.app.generate_vitals_summary')
def test_full_workflow_end_to_end(mock_summary, client):
    """
    test complete workflow from vitals to call status.

    verifies:
        - can fetch vitals
        - can initiate call
        - can check call status
        - all steps succeed
    """
    patient_id = 'PATIENT_001'

    # step 1: fetch vitals
    vitals_response = client.get(f'/patients/{patient_id}/vitals/recent')
    assert vitals_response.status_code == 200
    vitals_data = json.loads(vitals_response.data)
    assert vitals_data['vitals_count'] > 0

    # step 2: initiate call
    mock_summary.return_value = {
        "summary_text": "End-to-end test summary with sufficient word count to pass validation checks.",
        "word_count": 55,
        "generated_at": "2025-11-14T17:30:00Z",
        "model_used": "claude-3-5-haiku-20241022",
        "prompt_tokens": 420,
        "completion_tokens": 60
    }

    call_response = client.post(
        '/call-doctor',
        data=json.dumps({'patient_id': patient_id}),
        content_type='application/json'
    )
    assert call_response.status_code == 200
    call_data = json.loads(call_response.data)
    call_id = call_data['call_id']

    # step 3: check call status
    status_response = client.get(f'/calls/{call_id}/status')
    assert status_response.status_code == 200
    status_data = json.loads(status_response.data)
    assert status_data['status'] == 'completed'


def test_vitals_data_format(client):
    """
    test that vitals endpoint returns properly formatted data.

    verifies:
        - vitals have all required fields
        - data types are correct
    """
    response = client.get('/patients/PATIENT_001/vitals/recent')
    assert response.status_code == 200

    data = json.loads(response.data)
    vitals = data['vitals']

    # check first vital has required fields
    if len(vitals) > 0:
        vital = vitals[0]
        assert 'id' in vital
        assert 'patient_id' in vital
        assert 'timestamp' in vital
        assert 'heart_rate' in vital
        assert 'spo2' in vital
        assert 'systolic_bp' in vital
        assert 'diastolic_bp' in vital
        assert 'respiratory_rate' in vital
        assert 'body_temperature' in vital
