"""
vitals summary generation service using anthropic claude.

generates concise, clinically-relevant summaries of patient vital signs
for delivery to medical providers. uses llm for natural language summarization
while enforcing strict constraints against diagnosis or treatment recommendations.
"""

import os
import statistics
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from anthropic import Anthropic
import time


# configuration constants
MAX_SUMMARY_WORDS = 200
MIN_SUMMARY_WORDS = 50
MAX_SUMMARY_WORDS_BUFFER = 250
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 300
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2.0
MODEL_NAME = "claude-3-5-haiku-20241022"  # haiku for speed/cost


# custom exceptions
class SummaryServiceError(Exception):
    """base exception for summary service."""
    pass


class InvalidInputError(SummaryServiceError):
    """raised when input data is invalid."""
    pass


class APIError(SummaryServiceError):
    """raised when claude api call fails."""
    pass


class ValidationError(SummaryServiceError):
    """raised when generated summary fails validation."""
    pass


def format_vitals_for_prompt(
    vitals: List[Any],
    risk_assessment: dict
) -> Dict[str, Any]:
    """
    extract and format vital statistics from raw data for prompt construction.

    analyzes vitals to compute summary statistics and detect trends by comparing
    first 25% vs last 25% of readings.

    args:
        vitals: list of vital model instances
        risk_assessment: output from assess_risk() containing risk_level and signals

    returns:
        dict containing formatted statistics and metadata:
            - time window (start_time, end_time)
            - reading count
            - avg/min/max for each vital sign
            - trend ("deteriorating", "stable", "improving")
            - risk info
    """
    if not vitals:
        raise InvalidInputError("vitals list cannot be empty")

    num_readings = len(vitals)
    start_time = vitals[0].timestamp
    end_time = vitals[-1].timestamp

    # compute summary statistics from risk_assessment if available
    vitals_summary = risk_assessment.get("vitals_summary", {})

    # trend detection: compare first 25% vs last 25%
    split_point = max(1, num_readings // 4)
    first_segment = vitals[:split_point]
    last_segment = vitals[-split_point:]

    # key vitals for trend: hr, spo2, systolic bp
    hr_first = statistics.mean([v.heart_rate for v in first_segment])
    hr_last = statistics.mean([v.heart_rate for v in last_segment])

    spo2_first = statistics.mean([v.spo2 for v in first_segment])
    spo2_last = statistics.mean([v.spo2 for v in last_segment])

    sys_first = statistics.mean([v.systolic_bp for v in first_segment])
    sys_last = statistics.mean([v.systolic_bp for v in last_segment])

    # determine trend
    # deteriorating if: hr up >10, spo2 down >2, or systolic up >10
    hr_change = hr_last - hr_first
    spo2_change = spo2_last - spo2_first
    sys_change = sys_last - sys_first

    if hr_change > 10 or spo2_change < -2 or sys_change > 10:
        trend = "deteriorating"
    elif hr_change < -10 or spo2_change > 2 or sys_change < -10:
        trend = "improving"
    else:
        trend = "stable"

    # get patient context from first vital
    patient_context = {
        "age": vitals[0].age,
        "gender": vitals[0].gender
    }

    return {
        "start_time": start_time.strftime("%H:%M") if start_time else "unknown",
        "end_time": end_time.strftime("%H:%M") if end_time else "unknown",
        "num_readings": num_readings,
        "hr_avg": vitals_summary.get("heart_rate_avg", 0),
        "hr_min": vitals_summary.get("heart_rate_min", 0),
        "hr_max": vitals_summary.get("heart_rate_max", 0),
        "spo2_avg": vitals_summary.get("spo2_avg", 0),
        "spo2_min": vitals_summary.get("spo2_min", 0),
        "spo2_max": vitals_summary.get("spo2_max", 0),
        "systolic_avg": vitals_summary.get("systolic_bp_avg", 0),
        "systolic_min": vitals_summary.get("systolic_bp_min", 0),
        "systolic_max": vitals_summary.get("systolic_bp_max", 0),
        "diastolic_avg": vitals_summary.get("diastolic_bp_avg", 0),
        "diastolic_min": vitals_summary.get("diastolic_bp_min", 0),
        "diastolic_max": vitals_summary.get("diastolic_bp_max", 0),
        "rr_avg": vitals_summary.get("respiratory_rate_avg", 0),
        "rr_min": vitals_summary.get("respiratory_rate_min", 0),
        "rr_max": vitals_summary.get("respiratory_rate_max", 0),
        "temp_avg": vitals_summary.get("temperature_avg", 0),
        "temp_min": vitals_summary.get("temperature_min", 0),
        "temp_max": vitals_summary.get("temperature_max", 0),
        "trend": trend,
        "age": patient_context["age"],
        "gender": patient_context["gender"],
        "risk_level": risk_assessment.get("risk_level", "unknown"),
        "signals": risk_assessment.get("signals", [])
    }


def build_summary_prompt(
    patient_id: str,
    vitals_data: Dict[str, Any]
) -> Tuple[str, str]:
    """
    construct system and user prompts for claude summarization.

    creates carefully engineered prompts that enforce constraints against
    diagnosis/treatment while producing natural, informative summaries.

    args:
        patient_id: patient identifier
        vitals_data: formatted vitals statistics from format_vitals_for_prompt()

    returns:
        tuple of (system_prompt, user_prompt)
    """
    system_prompt = """you are a medical data summarization assistant for an automated patient monitoring system.

your role:
- summarize vital signs data in clear, neutral language
- highlight concerning trends objectively
- use terminology appropriate for healthcare professionals

critical constraints:
- you are NOT a doctor and must NOT provide diagnoses
- you must NOT recommend treatments or interventions
- only describe what the data shows, not what it means clinically
- use phrases like "data shows" or "vitals indicate" not "patient has" or "diagnosis of"

output requirements:
- maximum 200 words
- 2-3 short paragraphs
- professional medical terminology
- neutral, objective tone
- suitable for text-to-speech phone delivery"""

    # build signals section
    signals_text = ""
    if vitals_data["signals"]:
        signals_list = "\n".join([f"- {signal}" for signal in vitals_data["signals"]])
        signals_text = f"\n\nconcerning patterns detected:\n{signals_list}"

    user_prompt = f"""generate a summary for patient {patient_id} based on the following data:

time window: last 2 hours ({vitals_data['start_time']} to {vitals_data['end_time']})
total readings: {vitals_data['num_readings']}

vital signs summary:
- heart rate: avg {vitals_data['hr_avg']:.1f} bpm (range: {vitals_data['hr_min']:.1f}-{vitals_data['hr_max']:.1f})
- oxygen saturation: avg {vitals_data['spo2_avg']:.1f}% (range: {vitals_data['spo2_min']:.1f}-{vitals_data['spo2_max']:.1f}%)
- blood pressure: avg {vitals_data['systolic_avg']:.0f}/{vitals_data['diastolic_avg']:.0f} mmhg (systolic range: {vitals_data['systolic_min']:.0f}-{vitals_data['systolic_max']:.0f})
- respiratory rate: avg {vitals_data['rr_avg']:.1f} breaths/min (range: {vitals_data['rr_min']:.1f}-{vitals_data['rr_max']:.1f})
- temperature: avg {vitals_data['temp_avg']:.1f}°c (range: {vitals_data['temp_min']:.1f}-{vitals_data['temp_max']:.1f})

overall trend: {vitals_data['trend']}
risk assessment: {vitals_data['risk_level']}{signals_text}

patient context: {vitals_data['age']} year old {vitals_data['gender']}

generate a concise summary (max 200 words) suitable for a phone call to a healthcare provider.
include: time window, overall trend, key vital statistics, and any concerning patterns."""

    return system_prompt, user_prompt


def call_claude_api(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE
) -> Dict[str, Any]:
    """
    make http call to anthropic claude api with retry logic.

    implements exponential backoff retry for transient failures.
    uses haiku model for fast, cost-effective summarization.

    args:
        system_prompt: system instructions
        user_prompt: user message with vitals data
        max_tokens: response length limit (default 300)
        temperature: creativity level (default 0.3 for factual output)

    returns:
        dict containing:
            - content: generated summary text
            - model: model name used
            - usage: token usage statistics

    raises:
        APIError: if api call fails after retries
        ValueError: if ANTHROPIC_API_KEY not set
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    last_error = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # extract text content from response
            content = ""
            if response.content and len(response.content) > 0:
                first_block = response.content[0]
                # access text attribute if it exists (TextBlock)
                content = getattr(first_block, 'text', "")

            return {
                "content": content,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except Exception as e:
            last_error = e

            # don't retry on auth errors
            if "401" in str(e) or "authentication" in str(e).lower():
                raise APIError(f"authentication failed: {e}")

            # retry on rate limits, server errors, timeouts
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                wait_time = RETRY_BACKOFF_FACTOR ** attempt
                time.sleep(wait_time)
                continue

    # all retries failed
    raise APIError(f"claude api call failed after {RETRY_MAX_ATTEMPTS} attempts: {last_error}")


def validate_summary(summary_text: str, patient_id: str) -> Tuple[bool, Optional[str]]:
    """
    ensure generated summary meets requirements.

    performs relaxed validation that allows diagnosis/treatment terms
    when used in neutral context (e.g., in quotes or as data description).

    args:
        summary_text: generated summary text
        patient_id: patient identifier to check for

    returns:
        tuple of (is_valid, error_message)
            - (true, none) if valid
            - (false, error_message) if invalid
    """
    if not summary_text:
        return False, "summary is empty"

    # word count check
    word_count = len(summary_text.split())
    if word_count < MIN_SUMMARY_WORDS:
        return False, f"summary too short ({word_count} words, minimum {MIN_SUMMARY_WORDS})"
    if word_count > MAX_SUMMARY_WORDS_BUFFER:
        return False, f"summary too long ({word_count} words, maximum {MAX_SUMMARY_WORDS_BUFFER})"

    # check for patient id reference
    if patient_id.upper() not in summary_text.upper():
        return False, f"summary does not reference patient {patient_id}"

    # relaxed validation: only flag if terms appear in problematic context
    # allow terms like "data shows elevated readings" but not "patient is diagnosed with"

    # strict diagnosis patterns (not allowed)
    strict_diagnosis_patterns = [
        "diagnosed with",
        "diagnosis of",
        "patient has",
        "patient is suffering",
        "condition is"
    ]

    summary_lower = summary_text.lower()
    for pattern in strict_diagnosis_patterns:
        if pattern in summary_lower:
            return False, f"contains diagnostic language: '{pattern}'"

    # strict treatment patterns (not allowed)
    strict_treatment_patterns = [
        "recommend treatment",
        "prescribe",
        "administer",
        "should be given",
        "requires medication"
    ]

    for pattern in strict_treatment_patterns:
        if pattern in summary_lower:
            return False, f"contains treatment recommendation: '{pattern}'"

    # check for time reference (should mention time window or hours)
    time_keywords = ["hour", "time", "period", "window", "monitoring"]
    has_time_ref = any(keyword in summary_lower for keyword in time_keywords)
    if not has_time_ref:
        return False, "summary does not mention time window"

    # check for risk level mention
    risk_keywords = ["risk", "low", "moderate", "high", "normal", "concerning"]
    has_risk_ref = any(keyword in summary_lower for keyword in risk_keywords)
    if not has_risk_ref:
        return False, "summary does not mention risk assessment"

    return True, None


def generate_vitals_summary(
    patient_id: str,
    vitals: List[Any],
    risk_assessment: dict,
    patient_context: Optional[dict] = None
) -> Dict[str, Any]:
    """
    orchestrate the full summary generation workflow.

    coordinates vitals formatting, prompt construction, api call,
    and validation to produce a clinically-relevant summary.

    args:
        patient_id: patient identifier (e.g., "PATIENT_001")
        vitals: list of vital model instances from repository
        risk_assessment: output from assess_risk() containing risk_level and signals
        patient_context: optional additional metadata (unused in mvp)

    returns:
        dict containing:
            - summary_text: generated summary (max 200 words)
            - word_count: number of words in summary
            - generated_at: iso timestamp of generation
            - model_used: claude model name
            - prompt_tokens: input token count
            - completion_tokens: output token count

    raises:
        InvalidInputError: if inputs are invalid
        APIError: if claude api call fails
        ValidationError: if generated summary fails validation
    """
    # validate inputs
    if not patient_id:
        raise InvalidInputError("patient_id cannot be empty")
    if not vitals:
        raise InvalidInputError("vitals list cannot be empty")
    if not risk_assessment:
        raise InvalidInputError("risk_assessment cannot be empty")

    # format vitals data
    vitals_data = format_vitals_for_prompt(vitals, risk_assessment)

    # build prompts
    system_prompt, user_prompt = build_summary_prompt(patient_id, vitals_data)

    # call claude api
    api_response = call_claude_api(system_prompt, user_prompt)

    summary_text = api_response["content"]

    # validate summary
    is_valid, error_msg = validate_summary(summary_text, patient_id)
    if not is_valid:
        raise ValidationError(f"generated summary failed validation: {error_msg}")

    # compute word count
    word_count = len(summary_text.split())

    # return structured result
    return {
        "summary_text": summary_text,
        "word_count": word_count,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model_used": api_response["model"],
        "prompt_tokens": api_response["usage"]["input_tokens"],
        "completion_tokens": api_response["usage"]["output_tokens"]
    }
