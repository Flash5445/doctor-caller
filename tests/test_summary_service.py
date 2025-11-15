"""
tests for vitals summary generation service.

tests prompt building, api integration (mocked), validation,
and end-to-end summary generation workflow.
"""

import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.append("/Users/gurnoor/Desktop/doctor-caller")

import pytest
from backend.models.vitals import Vital
from backend.services.summary_service import (
    format_vitals_for_prompt,
    build_summary_prompt,
    call_claude_api,
    validate_summary,
    generate_vitals_summary,
    InvalidInputError,
    APIError,
    ValidationError,
)
from backend.services.risk_engine import assess_risk


def _create_mock_vital(
    patient_id: str = "PATIENT_001",
    timestamp: datetime = None,
    heart_rate: float = 75.0,
    respiratory_rate: float = 16.0,
    body_temperature: float = 36.8,
    spo2: float = 98.0,
    systolic_bp: int = 120,
    diastolic_bp: int = 80,
    age: int = 45,
    gender: str = "M"
) -> Vital:
    """
    create a mock vital record for testing.

    args:
        patient_id: patient identifier
        timestamp: vital timestamp
        heart_rate: heart rate in bpm
        respiratory_rate: respiratory rate in breaths/min
        body_temperature: temperature in celsius
        spo2: oxygen saturation percentage
        systolic_bp: systolic blood pressure in mmhg
        diastolic_bp: diastolic blood pressure in mmhg
        age: patient age
        gender: patient gender

    returns:
        vital instance with specified values
    """
    vital = Vital()
    vital.patient_id = patient_id
    vital.timestamp = timestamp or datetime.utcnow()
    vital.heart_rate = heart_rate
    vital.respiratory_rate = respiratory_rate
    vital.body_temperature = body_temperature
    vital.spo2 = spo2
    vital.systolic_bp = systolic_bp
    vital.diastolic_bp = diastolic_bp
    vital.age = age
    vital.gender = gender
    vital.pulse_pressure = systolic_bp - diastolic_bp
    vital.mean_arterial_pressure = diastolic_bp + (systolic_bp - diastolic_bp) / 3

    return vital


def test_format_vitals_for_prompt_with_normal_vitals():
    """
    test formatting normal vitals into prompt data structure.

    verifies:
        - correct statistics extraction
        - trend detection for stable vitals
        - patient context inclusion
    """
    # create 10 vitals with normal, stable values
    vitals = [
        _create_mock_vital(
            timestamp=datetime.utcnow() - timedelta(minutes=i * 12)
        )
        for i in range(10)
    ]

    risk = assess_risk(vitals)
    result = format_vitals_for_prompt(vitals, risk)

    assert result["num_readings"] == 10
    assert result["hr_avg"] == 75.0
    assert result["trend"] == "stable", "normal vitals should show stable trend"
    assert result["age"] == 45
    assert result["gender"] == "M"
    assert result["risk_level"] == "low"


def test_format_vitals_for_prompt_detects_deteriorating_trend():
    """
    test trend detection for deteriorating vitals.

    verifies:
        - correctly identifies deteriorating pattern
        - based on first 25% vs last 25% comparison
    """
    vitals = []
    base_time = datetime.utcnow()

    # first 25%: normal values
    for i in range(3):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=70.0,
            spo2=98.0,
            systolic_bp=115
        ))

    # middle: transitioning
    for i in range(3, 7):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=85.0,
            spo2=94.0,
            systolic_bp=125
        ))

    # last 25%: deteriorated
    for i in range(7, 10):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=95.0,
            spo2=91.0,
            systolic_bp=135
        ))

    risk = assess_risk(vitals)
    result = format_vitals_for_prompt(vitals, risk)

    assert result["trend"] == "deteriorating", "should detect deteriorating trend"


def test_format_vitals_for_prompt_detects_improving_trend():
    """
    test trend detection for improving vitals.

    verifies:
        - correctly identifies improving pattern
    """
    vitals = []
    base_time = datetime.utcnow()

    # first 25%: elevated values
    for i in range(3):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=95.0,
            spo2=91.0,
            systolic_bp=135
        ))

    # middle: improving
    for i in range(3, 7):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=85.0,
            spo2=94.0,
            systolic_bp=125
        ))

    # last 25%: normal
    for i in range(7, 10):
        vitals.append(_create_mock_vital(
            timestamp=base_time - timedelta(minutes=i * 12),
            heart_rate=70.0,
            spo2=98.0,
            systolic_bp=115
        ))

    risk = assess_risk(vitals)
    result = format_vitals_for_prompt(vitals, risk)

    assert result["trend"] == "improving", "should detect improving trend"


def test_format_vitals_for_prompt_raises_on_empty_vitals():
    """
    test error handling for empty vitals list.

    verifies:
        - raises InvalidInputError for empty input
    """
    with pytest.raises(InvalidInputError, match="vitals list cannot be empty"):
        format_vitals_for_prompt([], {})


def test_build_summary_prompt_structure():
    """
    test prompt construction produces correct structure.

    verifies:
        - returns tuple of (system_prompt, user_prompt)
        - prompts contain expected content
        - patient data is formatted correctly
    """
    vitals = [_create_mock_vital() for _ in range(10)]
    risk = assess_risk(vitals)
    vitals_data = format_vitals_for_prompt(vitals, risk)

    system_prompt, user_prompt = build_summary_prompt("PATIENT_001", vitals_data)

    # check system prompt
    assert isinstance(system_prompt, str)
    assert "summarization assistant" in system_prompt.lower()
    assert "not a doctor" in system_prompt.lower()
    assert "must not provide diagnoses" in system_prompt.lower()

    # check user prompt
    assert isinstance(user_prompt, str)
    assert "PATIENT_001" in user_prompt
    assert "heart rate" in user_prompt.lower()
    assert "oxygen saturation" in user_prompt.lower()
    assert "blood pressure" in user_prompt.lower()
    assert "risk assessment" in user_prompt.lower()


def test_build_summary_prompt_includes_signals():
    """
    test that concerning signals are included in prompt when present.

    verifies:
        - signals section added when risk signals exist
    """
    vitals = [_create_mock_vital(heart_rate=125.0) for _ in range(10)]
    risk = assess_risk(vitals)  # should generate signal
    vitals_data = format_vitals_for_prompt(vitals, risk)

    system_prompt, user_prompt = build_summary_prompt("PATIENT_001", vitals_data)

    assert "concerning patterns" in user_prompt.lower()


def test_validate_summary_accepts_valid_summary():
    """
    test validation accepts properly formatted summary.

    verifies:
        - valid summary passes all checks
        - returns (true, none)
    """
    valid_summary = """Patient PATIENT_001 vital signs from 15:30 to 17:30 show stable measurements over the two hour monitoring period.
    Heart rate averaged 72 bpm with range 68-78 bpm, oxygen saturation maintained at 98% throughout with range 97-99%, blood pressure steady at 120/80 mmHg, respiratory rate 16 breaths per minute, temperature 36.8 degrees celsius.
    Risk assessment: low. All vitals remained within normal ranges with minimal variation demonstrating good physiological stability."""

    is_valid, error = validate_summary(valid_summary, "PATIENT_001")

    assert is_valid is True
    assert error is None


def test_validate_summary_rejects_too_short():
    """
    test validation rejects summaries under minimum word count.

    verifies:
        - summaries <50 words rejected
    """
    short_summary = "Patient PATIENT_001 vitals normal."

    is_valid, error = validate_summary(short_summary, "PATIENT_001")

    assert is_valid is False
    assert "too short" in error.lower()


def test_validate_summary_rejects_too_long():
    """
    test validation rejects summaries over maximum word count.

    verifies:
        - summaries >250 words rejected
    """
    # create a summary with >250 words
    long_summary = "Patient PATIENT_001 " + " ".join(["vitals"] * 260)

    is_valid, error = validate_summary(long_summary, "PATIENT_001")

    assert is_valid is False
    assert "too long" in error.lower()


def test_validate_summary_rejects_diagnostic_language():
    """
    test validation rejects strict diagnostic patterns.

    verifies:
        - phrases like "diagnosed with" rejected
        - phrases like "patient has" rejected
    """
    diagnostic_summary = """Patient PATIENT_001 vital signs from 15:30 to 17:30 over 2 hours monitoring period show elevated heart rate patterns.
    The patient is diagnosed with tachycardia based on sustained elevated heart rate averaging 125 bpm with maximum readings reaching 135 bpm.
    Blood pressure readings remained normal at 120/80 mmHg, oxygen saturation 98%, respiratory rate 16 breaths per minute, temperature stable at 36.8 degrees.
    Risk assessment moderate due to cardiac concerns."""

    is_valid, error = validate_summary(diagnostic_summary, "PATIENT_001")

    assert is_valid is False
    assert "diagnostic language" in error.lower()


def test_validate_summary_rejects_treatment_recommendations():
    """
    test validation rejects treatment recommendation patterns.

    verifies:
        - phrases like "recommend treatment" rejected
        - phrases like "prescribe" rejected
    """
    treatment_summary = """Patient PATIENT_001 vitals from 15:30 to 17:30 show elevated heart rate averaging 125 bpm over two hour monitoring period.
    Recommend treatment with beta blockers to reduce heart rate and bring it within normal range of 60-100 bpm for optimal cardiac function.
    Blood pressure readings remained normal at 120/80 mmHg, oxygen saturation 98%, temperature stable. Risk assessment moderate over monitoring period due to sustained tachycardia."""

    is_valid, error = validate_summary(treatment_summary, "PATIENT_001")

    assert is_valid is False
    assert "treatment recommendation" in error.lower()


def test_validate_summary_requires_patient_id():
    """
    test validation requires patient id reference.

    verifies:
        - summary without patient id rejected
    """
    no_id_summary = """Vital signs from 15:30 to 17:30 show stable measurements over two hours monitoring period with consistent readings.
    Heart rate averaged 72 bpm with range 68-78 bpm, oxygen saturation maintained at 98% throughout, blood pressure steady at 120/80 mmHg, respiratory rate 16 breaths per minute.
    Risk assessment: low. All vitals remained within normal ranges throughout the entire monitoring period demonstrating good stability."""

    is_valid, error = validate_summary(no_id_summary, "PATIENT_001")

    assert is_valid is False
    assert "does not reference patient" in error.lower()


def test_validate_summary_requires_time_reference():
    """
    test validation requires time window mention.

    verifies:
        - summary without time reference rejected
    """
    no_time_summary = """Patient PATIENT_001 vital signs show stable measurements across all recorded readings with consistent values.
    Heart rate averaged 72 bpm with range 68-78 bpm, oxygen saturation maintained at 98% with range 97-99%, blood pressure steady at 120/80 mmHg.
    Risk assessment: low. All vitals remained within normal ranges demonstrating good physiological stability and homeostasis."""

    is_valid, error = validate_summary(no_time_summary, "PATIENT_001")

    assert is_valid is False
    assert "does not mention time" in error.lower()


def test_validate_summary_requires_risk_reference():
    """
    test validation requires risk assessment mention.

    verifies:
        - summary without risk reference rejected
    """
    no_risk_summary = """Patient PATIENT_001 vital signs from 15:30 to 17:30 over 2 hours monitoring period show stable measurements.
    Heart rate averaged 72 bpm with range 68-78 bpm, oxygen saturation maintained at 98% with range 97-99%, blood pressure steady at 120/80 mmHg, respiratory rate 16 breaths per minute.
    All vitals show stable measurements throughout the monitoring period with minimal variation and good physiological control."""

    is_valid, error = validate_summary(no_risk_summary, "PATIENT_001")

    assert is_valid is False
    assert "does not mention risk" in error.lower()


@patch('backend.services.summary_service.Anthropic')
def test_call_claude_api_success(mock_anthropic_class):
    """
    test successful claude api call.

    verifies:
        - api called with correct parameters
        - response properly extracted
        - usage stats returned
    """
    # mock the response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is a test summary.")]
    mock_response.model = "claude-3-5-haiku-20241022"
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    # set api key
    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    result = call_claude_api("system prompt", "user prompt")

    assert result["content"] == "This is a test summary."
    assert result["model"] == "claude-3-5-haiku-20241022"
    assert result["usage"]["input_tokens"] == 100
    assert result["usage"]["output_tokens"] == 50

    # verify api was called
    mock_client.messages.create.assert_called_once()


@patch('backend.services.summary_service.Anthropic')
def test_call_claude_api_missing_key(mock_anthropic_class):
    """
    test api call fails without api key.

    verifies:
        - raises ValueError when ANTHROPIC_API_KEY not set
    """
    import os
    # temporarily remove api key
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        call_claude_api("system", "user")

    # restore key
    if old_key:
        os.environ["ANTHROPIC_API_KEY"] = old_key


@patch('backend.services.summary_service.Anthropic')
def test_generate_vitals_summary_with_normal_vitals(mock_anthropic_class):
    """
    test end-to-end summary generation with normal vitals.

    verifies:
        - full workflow executes successfully
        - returns properly structured result
        - includes all expected fields
    """
    # setup mock
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="""Patient PATIENT_001 vital signs from 00:00 to 02:00 show stable measurements over the two hour monitoring period with consistent readings throughout.
Heart rate averaged 75 bpm with range 75-75 bpm, oxygen saturation maintained at 98%, blood pressure steady at 120/80 mmHg, respiratory rate 16 breaths per minute, temperature 36.8°C.
Risk assessment: low. All vitals remained within normal ranges demonstrating good physiological stability.""")]
    mock_response.model = "claude-3-5-haiku-20241022"
    mock_response.usage = MagicMock(input_tokens=450, output_tokens=70)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    # create vitals and risk assessment
    vitals = [_create_mock_vital() for _ in range(10)]
    risk = assess_risk(vitals)

    result = generate_vitals_summary("PATIENT_001", vitals, risk)

    # verify result structure
    assert "summary_text" in result
    assert "word_count" in result
    assert "generated_at" in result
    assert "model_used" in result
    assert "prompt_tokens" in result
    assert "completion_tokens" in result

    assert "PATIENT_001" in result["summary_text"]
    assert result["word_count"] > 50
    assert result["model_used"] == "claude-3-5-haiku-20241022"


@patch('backend.services.summary_service.Anthropic')
def test_generate_vitals_summary_with_high_risk(mock_anthropic_class):
    """
    test summary generation with high risk vitals.

    verifies:
        - handles concerning vitals correctly
        - signals included in prompt
    """
    # setup mock
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="""Patient PATIENT_001 vital signs from 00:00 to 02:00 show deteriorating trend with multiple concerning patterns over the two hour monitoring period.
Heart rate elevated averaging 135 bpm with range 135-135 bpm, maximum readings sustained throughout. Oxygen saturation low at 88% average with range 88-88%.
Risk assessment: high. Data shows sustained tachycardia and hypoxia with concerning vital sign abnormalities requiring immediate medical attention and review.""")]
    mock_response.model = "claude-3-5-haiku-20241022"
    mock_response.usage = MagicMock(input_tokens=500, output_tokens=80)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    # create high-risk vitals
    vitals = [
        _create_mock_vital(heart_rate=135.0, spo2=88.0)
        for _ in range(10)
    ]
    risk = assess_risk(vitals)

    result = generate_vitals_summary("PATIENT_001", vitals, risk)

    assert "summary_text" in result
    assert "high" in result["summary_text"].lower() or "concern" in result["summary_text"].lower()


def test_generate_vitals_summary_validates_inputs():
    """
    test input validation in generate_vitals_summary.

    verifies:
        - raises InvalidInputError for missing patient_id
        - raises InvalidInputError for empty vitals
        - raises InvalidInputError for missing risk_assessment
    """
    vitals = [_create_mock_vital() for _ in range(10)]
    risk = assess_risk(vitals)

    # missing patient_id
    with pytest.raises(InvalidInputError, match="patient_id cannot be empty"):
        generate_vitals_summary("", vitals, risk)

    # empty vitals
    with pytest.raises(InvalidInputError, match="vitals list cannot be empty"):
        generate_vitals_summary("PATIENT_001", [], risk)

    # missing risk_assessment
    with pytest.raises(InvalidInputError, match="risk_assessment cannot be empty"):
        generate_vitals_summary("PATIENT_001", vitals, None)
