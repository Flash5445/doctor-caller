"""
tests for twilio call service.

tests all call service functionality with mocked twilio client,
including call initiation, status tracking, and error handling.
"""

import sys
import os
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

import pytest
from twilio.base.exceptions import TwilioRestException
from backend.services.call_service import TwilioCallService


@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    set up mock environment variables for twilio.

    args:
        monkeypatch: pytest monkeypatch fixture

    yields:
        dict with mock environment variable values
    """
    env_vars = {
        'TWILIO_ACCOUNT_SID': 'ACtest1234567890abcdef1234567890ab',
        'TWILIO_AUTH_TOKEN': 'test_auth_token_12345',
        'TWILIO_CALLER_ID': '+15551234567',
        'PROVIDER_PHONE_NUMBER': '+15559876543',
        'WEBHOOK_BASE_URL': 'https://test.ngrok.io'
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    yield env_vars

    # cleanup
    for key in env_vars.keys():
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_twilio_client():
    """
    create mock twilio client.

    returns:
        mocked twilio client with call creation methods
    """
    mock_client = MagicMock()

    # mock call creation
    mock_call = MagicMock()
    mock_call.sid = 'CA1234567890abcdef1234567890abcdef'
    mock_call.status = 'queued'
    mock_call.duration = None

    mock_client.calls.create.return_value = mock_call

    # mock call fetch
    mock_client.calls.return_value.fetch.return_value = mock_call

    return mock_client


def test_initialization_success(mock_env_vars):
    """
    test successful initialization with valid env vars.

    verifies:
        - service initializes with all required env vars
        - twilio client is created
        - empty call storage is initialized
    """
    with patch('backend.services.call_service.Client') as mock_client_class:
        service = TwilioCallService()

        assert service.account_sid == mock_env_vars['TWILIO_ACCOUNT_SID']
        assert service.auth_token == mock_env_vars['TWILIO_AUTH_TOKEN']
        assert service.caller_id == mock_env_vars['TWILIO_CALLER_ID']
        assert service.provider_number == mock_env_vars['PROVIDER_PHONE_NUMBER']
        assert service.webhook_base_url == mock_env_vars['WEBHOOK_BASE_URL']
        assert service.calls == {}

        # verify client was instantiated
        mock_client_class.assert_called_once_with(
            mock_env_vars['TWILIO_ACCOUNT_SID'],
            mock_env_vars['TWILIO_AUTH_TOKEN']
        )


def test_initialization_missing_env_vars(monkeypatch):
    """
    test initialization fails with missing env vars.

    verifies:
        - raises ValueError when required env vars missing
    """
    # set only some env vars
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest123')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'token123')
    # missing TWILIO_CALLER_ID and PROVIDER_PHONE_NUMBER

    with pytest.raises(ValueError) as exc_info:
        TwilioCallService()

    assert "missing required environment variables" in str(exc_info.value)


def test_initialization_webhook_default(monkeypatch):
    """
    test initialization uses default webhook url if not provided.

    verifies:
        - webhook_base_url defaults to http://localhost:5000
    """
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest123')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'token123')
    monkeypatch.setenv('TWILIO_CALLER_ID', '+15551234567')
    monkeypatch.setenv('PROVIDER_PHONE_NUMBER', '+15559876543')
    # don't set WEBHOOK_BASE_URL

    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()
        assert service.webhook_base_url == 'http://localhost:5000'


def test_start_call_success(mock_env_vars, mock_twilio_client):
    """
    test successful call initiation.

    verifies:
        - generates unique call_id
        - calls twilio api with correct parameters
        - stores call metadata
        - returns call_id
    """
    with patch('backend.services.call_service.Client', return_value=mock_twilio_client):
        service = TwilioCallService()

        summary_text = "patient vitals summary for test patient."
        patient_id = "PATIENT_001"

        call_id = service.start_call(summary_text, patient_id)

        # verify call_id format
        assert call_id.startswith('call_')
        assert len(call_id) == 13  # 'call_' + 8 hex chars

        # verify twilio api was called
        mock_twilio_client.calls.create.assert_called_once()
        call_args = mock_twilio_client.calls.create.call_args[1]

        assert call_args['to'] == mock_env_vars['PROVIDER_PHONE_NUMBER']
        assert call_args['from_'] == mock_env_vars['TWILIO_CALLER_ID']
        assert call_args['url'] == f"{mock_env_vars['WEBHOOK_BASE_URL']}/twilio/voice?call_id={call_id}"
        assert call_args['method'] == 'POST'
        assert call_args['status_callback'] == f"{mock_env_vars['WEBHOOK_BASE_URL']}/twilio/status"
        assert call_args['status_callback_event'] == ['completed']
        assert call_args['status_callback_method'] == 'POST'

        # verify call metadata stored
        assert call_id in service.calls
        call_data = service.calls[call_id]
        assert call_data['call_id'] == call_id
        assert call_data['call_sid'] == 'CA1234567890abcdef1234567890abcdef'
        assert call_data['patient_id'] == patient_id
        assert call_data['summary_text'] == summary_text
        assert call_data['status'] == 'queued'
        assert call_data['to'] == mock_env_vars['PROVIDER_PHONE_NUMBER']
        assert call_data['from'] == mock_env_vars['TWILIO_CALLER_ID']
        assert call_data['created_at'] is not None
        assert call_data['completed_at'] is None
        assert call_data['duration_seconds'] is None


def test_start_call_twilio_error(mock_env_vars, mock_twilio_client):
    """
    test call initiation with twilio api error.

    verifies:
        - raises TwilioRestException on api error
    """
    # configure mock to raise exception
    mock_twilio_client.calls.create.side_effect = TwilioRestException(
        status=400,
        uri='/2010-04-01/Accounts/ACtest/Calls.json',
        msg='invalid phone number',
        code=21211
    )

    with patch('backend.services.call_service.Client', return_value=mock_twilio_client):
        service = TwilioCallService()

        with pytest.raises(TwilioRestException) as exc_info:
            service.start_call("test summary", "PATIENT_001")

        assert "twilio api error" in str(exc_info.value)


def test_get_call_status_existing_call(mock_env_vars, mock_twilio_client):
    """
    test retrieving status for existing call.

    verifies:
        - returns call data for existing call_id
        - queries twilio for latest status
        - updates local storage with twilio data
    """
    # configure mock for status update
    mock_updated_call = MagicMock()
    mock_updated_call.status = 'completed'
    mock_updated_call.duration = '120'
    mock_twilio_client.calls.return_value.fetch.return_value = mock_updated_call

    with patch('backend.services.call_service.Client', return_value=mock_twilio_client):
        service = TwilioCallService()

        # create a call first
        call_id = service.start_call("test summary", "PATIENT_001")

        # get status
        status_data = service.get_call_status(call_id)

        assert status_data is not None
        assert status_data['call_id'] == call_id
        assert status_data['call_sid'] == 'CA1234567890abcdef1234567890abcdef'
        assert status_data['status'] == 'completed'
        assert status_data['patient_id'] == 'PATIENT_001'
        assert status_data['duration_seconds'] == 120
        assert status_data['completed_at'] is not None

        # verify twilio fetch was called
        mock_twilio_client.calls.assert_called()


def test_get_call_status_nonexistent_call(mock_env_vars):
    """
    test retrieving status for non-existent call.

    verifies:
        - returns None for unknown call_id
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        status_data = service.get_call_status('nonexistent_call_id')

        assert status_data is None


def test_get_call_status_twilio_fetch_error(mock_env_vars, mock_twilio_client):
    """
    test get_call_status when twilio fetch fails.

    verifies:
        - returns stored data even if twilio fetch fails
        - does not raise exception
    """
    # configure mock to raise exception on fetch
    mock_twilio_client.calls.return_value.fetch.side_effect = TwilioRestException(
        status=404,
        uri='/2010-04-01/Accounts/ACtest/Calls/CA123.json',
        msg='call not found',
        code=20404
    )

    with patch('backend.services.call_service.Client', return_value=mock_twilio_client):
        service = TwilioCallService()

        # create a call
        call_id = service.start_call("test summary", "PATIENT_001")

        # get status (should not raise, return stored data)
        status_data = service.get_call_status(call_id)

        assert status_data is not None
        assert status_data['call_id'] == call_id
        assert status_data['status'] == 'queued'  # original stored status


def test_get_summary_for_call_success(mock_env_vars):
    """
    test retrieving summary text for existing call.

    verifies:
        - returns summary_text for existing call_id
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        summary_text = "this is a test summary for patient vitals."
        call_id = service.start_call(summary_text, "PATIENT_001")

        retrieved_summary = service.get_summary_for_call(call_id)

        assert retrieved_summary == summary_text


def test_get_summary_for_call_nonexistent(mock_env_vars):
    """
    test retrieving summary for non-existent call.

    verifies:
        - returns None for unknown call_id
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        retrieved_summary = service.get_summary_for_call('nonexistent_call_id')

        assert retrieved_summary is None


def test_map_twilio_status_queued(mock_env_vars):
    """
    test status mapping for queued status.

    verifies:
        - 'queued' maps to 'queued'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        mapped = service._map_twilio_status('queued')
        assert mapped == 'queued'


def test_map_twilio_status_ringing(mock_env_vars):
    """
    test status mapping for ringing status.

    verifies:
        - 'ringing' maps to 'initiated'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        mapped = service._map_twilio_status('ringing')
        assert mapped == 'initiated'


def test_map_twilio_status_in_progress(mock_env_vars):
    """
    test status mapping for in-progress status.

    verifies:
        - 'in-progress' maps to 'in-progress'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        mapped = service._map_twilio_status('in-progress')
        assert mapped == 'in-progress'


def test_map_twilio_status_completed(mock_env_vars):
    """
    test status mapping for completed status.

    verifies:
        - 'completed' maps to 'completed'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        mapped = service._map_twilio_status('completed')
        assert mapped == 'completed'


def test_map_twilio_status_failed_statuses(mock_env_vars):
    """
    test status mapping for various failure statuses.

    verifies:
        - 'busy', 'no-answer', 'failed', 'canceled' all map to 'failed'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        assert service._map_twilio_status('busy') == 'failed'
        assert service._map_twilio_status('no-answer') == 'failed'
        assert service._map_twilio_status('failed') == 'failed'
        assert service._map_twilio_status('canceled') == 'failed'


def test_map_twilio_status_unknown(mock_env_vars):
    """
    test status mapping for unknown status.

    verifies:
        - unknown statuses map to 'unknown'
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        mapped = service._map_twilio_status('some-unknown-status')
        assert mapped == 'unknown'


def test_clear_calls(mock_env_vars):
    """
    test clearing all stored calls.

    verifies:
        - clear_calls() removes all stored calls
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        # create some calls
        call_id_1 = service.start_call("summary 1", "PATIENT_001")
        call_id_2 = service.start_call("summary 2", "PATIENT_002")

        assert len(service.calls) == 2

        # clear calls
        service.clear_calls()

        assert len(service.calls) == 0
        assert service.get_call_status(call_id_1) is None
        assert service.get_call_status(call_id_2) is None


def test_multiple_calls_unique_ids(mock_env_vars):
    """
    test that multiple calls get unique call_ids.

    verifies:
        - each call gets unique call_id
        - all calls are stored independently
    """
    with patch('backend.services.call_service.Client'):
        service = TwilioCallService()

        call_ids = []
        for i in range(5):
            call_id = service.start_call(f"summary {i}", f"PATIENT_{i:03d}")
            call_ids.append(call_id)

        # verify all ids are unique
        assert len(call_ids) == len(set(call_ids))

        # verify all calls are stored
        assert len(service.calls) == 5

        # verify each call has correct patient_id
        for i, call_id in enumerate(call_ids):
            status = service.get_call_status(call_id)
            assert status['patient_id'] == f"PATIENT_{i:03d}"


def test_call_status_updates_from_twilio(mock_env_vars, mock_twilio_client):
    """
    test that get_call_status updates status from twilio.

    verifies:
        - status is updated from 'queued' to 'in-progress'
        - duration is updated when available
    """
    # initial call returns queued status
    initial_mock_call = MagicMock()
    initial_mock_call.sid = 'CA1234567890abcdef1234567890abcdef'
    initial_mock_call.status = 'queued'
    initial_mock_call.duration = None
    mock_twilio_client.calls.create.return_value = initial_mock_call

    # status fetch returns in-progress
    updated_mock_call = MagicMock()
    updated_mock_call.status = 'in-progress'
    updated_mock_call.duration = None
    mock_twilio_client.calls.return_value.fetch.return_value = updated_mock_call

    with patch('backend.services.call_service.Client', return_value=mock_twilio_client):
        service = TwilioCallService()

        call_id = service.start_call("test summary", "PATIENT_001")

        # initial status should be queued
        assert service.calls[call_id]['status'] == 'queued'

        # get status should update from twilio
        status_data = service.get_call_status(call_id)

        assert status_data['status'] == 'in-progress'
        assert service.calls[call_id]['status'] == 'in-progress'
