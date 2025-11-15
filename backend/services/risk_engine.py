"""
rule-based risk assessment engine for patient vital signs.

analyzes time-series vitals data and generates risk levels with supporting signals.
does not provide medical diagnosis - only data-driven risk flags.
"""

from typing import List, Optional, Dict, Any
import statistics


# threshold constants for vital signs
# two-tier system: mild (moderate risk) and extreme (high risk)

# heart rate thresholds (bpm)
HR_NORMAL_MIN = 60
HR_NORMAL_MAX = 100
HR_MILD_LOW = 50
HR_MILD_HIGH = 120
HR_EXTREME_LOW = 50
HR_EXTREME_HIGH = 120

# spo2 thresholds (%)
SPO2_NORMAL_MIN = 95
SPO2_MILD_MIN = 92
SPO2_EXTREME_MIN = 92

# blood pressure thresholds (mmhg)
SYSTOLIC_NORMAL_MIN = 90
SYSTOLIC_NORMAL_MAX = 140
SYSTOLIC_MILD_LOW = 85
SYSTOLIC_MILD_HIGH = 160
SYSTOLIC_EXTREME_LOW = 85
SYSTOLIC_EXTREME_HIGH = 160

DIASTOLIC_NORMAL_MIN = 60
DIASTOLIC_NORMAL_MAX = 90
DIASTOLIC_MILD_LOW = 50
DIASTOLIC_MILD_HIGH = 100
DIASTOLIC_EXTREME_LOW = 50
DIASTOLIC_EXTREME_HIGH = 100

# respiratory rate thresholds (breaths/min)
RR_NORMAL_MIN = 12
RR_NORMAL_MAX = 20
RR_MILD_LOW = 10
RR_MILD_HIGH = 24
RR_EXTREME_LOW = 10
RR_EXTREME_HIGH = 24

# temperature thresholds (celsius)
TEMP_NORMAL_MIN = 36.1
TEMP_NORMAL_MAX = 37.2
TEMP_MILD_LOW = 35.5
TEMP_MILD_HIGH = 38.0
TEMP_EXTREME_LOW = 35.5
TEMP_EXTREME_HIGH = 38.0

# sustained condition: percentage of readings that must exceed threshold
SUSTAINED_THRESHOLD_PCT = 0.4


def _check_sustained_condition(
    values: List[float],
    threshold: float,
    comparison: str = "greater"
) -> tuple[bool, float]:
    """
    check if a vital sign shows sustained abnormality.

    sustained means BOTH:
    - average exceeds threshold
    - at least 40% of readings exceed threshold

    args:
        values: list of vital sign measurements
        threshold: threshold value to compare against
        comparison: "greater" or "less" for threshold comparison

    returns:
        tuple of (is_sustained, percentage_exceeding)
    """
    if not values:
        return False, 0.0

    avg_value = statistics.mean(values)

    if comparison == "greater":
        exceeding_count = sum(1 for v in values if v > threshold)
        avg_exceeds = avg_value > threshold
    else:  # "less"
        exceeding_count = sum(1 for v in values if v < threshold)
        avg_exceeds = avg_value < threshold

    pct_exceeding = exceeding_count / len(values)
    is_sustained = avg_exceeds and pct_exceeding >= SUSTAINED_THRESHOLD_PCT

    return is_sustained, pct_exceeding


def _analyze_heart_rate(vitals: List[Any]) -> Optional[Dict[str, Any]]:
    """
    analyze heart rate for abnormalities.

    args:
        vitals: list of vital records

    returns:
        dict with severity and description if abnormal, none otherwise
    """
    if not vitals:
        return None

    hr_values = [v.heart_rate for v in vitals]
    avg_hr = statistics.mean(hr_values)
    min_hr = min(hr_values)
    max_hr = max(hr_values)

    # check for extreme tachycardia
    is_sustained_high, pct_high = _check_sustained_condition(
        hr_values, HR_EXTREME_HIGH, "greater"
    )
    if is_sustained_high:
        return {
            "severity": "extreme",
            "vital": "heart_rate",
            "description": f"elevated heart rate detected (avg: {avg_hr:.1f} bpm, max: {max_hr:.1f} bpm, {pct_high*100:.0f}% of readings > {HR_EXTREME_HIGH} bpm)"
        }

    # check for extreme bradycardia
    is_sustained_low, pct_low = _check_sustained_condition(
        hr_values, HR_EXTREME_LOW, "less"
    )
    if is_sustained_low:
        return {
            "severity": "extreme",
            "vital": "heart_rate",
            "description": f"low heart rate detected (avg: {avg_hr:.1f} bpm, min: {min_hr:.1f} bpm, {pct_low*100:.0f}% of readings < {HR_EXTREME_LOW} bpm)"
        }

    # check for mild tachycardia
    is_sustained_mild_high, pct_mild_high = _check_sustained_condition(
        hr_values, HR_NORMAL_MAX, "greater"
    )
    if is_sustained_mild_high and avg_hr < HR_EXTREME_HIGH:
        return {
            "severity": "mild",
            "vital": "heart_rate",
            "description": f"mildly elevated heart rate (avg: {avg_hr:.1f} bpm, {pct_mild_high*100:.0f}% of readings > {HR_NORMAL_MAX} bpm)"
        }

    # check for mild bradycardia
    is_sustained_mild_low, pct_mild_low = _check_sustained_condition(
        hr_values, HR_NORMAL_MIN, "less"
    )
    if is_sustained_mild_low and avg_hr > HR_EXTREME_LOW:
        return {
            "severity": "mild",
            "vital": "heart_rate",
            "description": f"mildly low heart rate (avg: {avg_hr:.1f} bpm, {pct_mild_low*100:.0f}% of readings < {HR_NORMAL_MIN} bpm)"
        }

    return None


def _analyze_spo2(vitals: List[Any]) -> Optional[Dict[str, Any]]:
    """
    analyze oxygen saturation for abnormalities.

    args:
        vitals: list of vital records

    returns:
        dict with severity and description if abnormal, none otherwise
    """
    if not vitals:
        return None

    spo2_values = [v.spo2 for v in vitals]
    avg_spo2 = statistics.mean(spo2_values)
    min_spo2 = min(spo2_values)

    # check for extreme hypoxia
    is_sustained_extreme, pct_extreme = _check_sustained_condition(
        spo2_values, SPO2_EXTREME_MIN, "less"
    )
    if is_sustained_extreme:
        return {
            "severity": "extreme",
            "vital": "spo2",
            "description": f"low oxygen saturation detected (avg: {avg_spo2:.1f}%, min: {min_spo2:.1f}%, {pct_extreme*100:.0f}% of readings < {SPO2_EXTREME_MIN}%)"
        }

    # check for mild hypoxia
    is_sustained_mild, pct_mild = _check_sustained_condition(
        spo2_values, SPO2_NORMAL_MIN, "less"
    )
    if is_sustained_mild and avg_spo2 >= SPO2_EXTREME_MIN:
        return {
            "severity": "mild",
            "vital": "spo2",
            "description": f"mildly low oxygen saturation (avg: {avg_spo2:.1f}%, min: {min_spo2:.1f}%, {pct_mild*100:.0f}% of readings < {SPO2_NORMAL_MIN}%)"
        }

    return None


def _analyze_blood_pressure(vitals: List[Any]) -> Optional[Dict[str, Any]]:
    """
    analyze blood pressure for abnormalities (both systolic and diastolic).

    args:
        vitals: list of vital records

    returns:
        dict with severity and description if abnormal, none otherwise
    """
    if not vitals:
        return None

    systolic_values = [v.systolic_bp for v in vitals]
    diastolic_values = [v.diastolic_bp for v in vitals]

    avg_sys = statistics.mean(systolic_values)
    avg_dia = statistics.mean(diastolic_values)
    min_sys = min(systolic_values)
    max_sys = max(systolic_values)
    min_dia = min(diastolic_values)
    max_dia = max(diastolic_values)

    # check systolic - extreme hypertension
    is_sustained_sys_high, pct_sys_high = _check_sustained_condition(
        systolic_values, SYSTOLIC_EXTREME_HIGH, "greater"
    )
    if is_sustained_sys_high:
        return {
            "severity": "extreme",
            "vital": "blood_pressure",
            "description": f"elevated systolic blood pressure (avg: {avg_sys:.0f} mmhg, max: {max_sys:.0f} mmhg, {pct_sys_high*100:.0f}% of readings > {SYSTOLIC_EXTREME_HIGH} mmhg)"
        }

    # check systolic - extreme hypotension
    is_sustained_sys_low, pct_sys_low = _check_sustained_condition(
        systolic_values, SYSTOLIC_EXTREME_LOW, "less"
    )
    if is_sustained_sys_low:
        return {
            "severity": "extreme",
            "vital": "blood_pressure",
            "description": f"low systolic blood pressure (avg: {avg_sys:.0f} mmhg, min: {min_sys:.0f} mmhg, {pct_sys_low*100:.0f}% of readings < {SYSTOLIC_EXTREME_LOW} mmhg)"
        }

    # check diastolic - extreme
    is_sustained_dia_high, pct_dia_high = _check_sustained_condition(
        diastolic_values, DIASTOLIC_EXTREME_HIGH, "greater"
    )
    if is_sustained_dia_high:
        return {
            "severity": "extreme",
            "vital": "blood_pressure",
            "description": f"elevated diastolic blood pressure (avg: {avg_dia:.0f} mmhg, max: {max_dia:.0f} mmhg, {pct_dia_high*100:.0f}% of readings > {DIASTOLIC_EXTREME_HIGH} mmhg)"
        }

    is_sustained_dia_low, pct_dia_low = _check_sustained_condition(
        diastolic_values, DIASTOLIC_EXTREME_LOW, "less"
    )
    if is_sustained_dia_low:
        return {
            "severity": "extreme",
            "vital": "blood_pressure",
            "description": f"low diastolic blood pressure (avg: {avg_dia:.0f} mmhg, min: {min_dia:.0f} mmhg, {pct_dia_low*100:.0f}% of readings < {DIASTOLIC_EXTREME_LOW} mmhg)"
        }

    # check mild systolic abnormalities
    is_sustained_sys_mild_high, pct_sys_mild_high = _check_sustained_condition(
        systolic_values, SYSTOLIC_NORMAL_MAX, "greater"
    )
    if is_sustained_sys_mild_high and avg_sys < SYSTOLIC_EXTREME_HIGH:
        return {
            "severity": "mild",
            "vital": "blood_pressure",
            "description": f"mildly elevated systolic blood pressure (avg: {avg_sys:.0f} mmhg, {pct_sys_mild_high*100:.0f}% of readings > {SYSTOLIC_NORMAL_MAX} mmhg)"
        }

    is_sustained_sys_mild_low, pct_sys_mild_low = _check_sustained_condition(
        systolic_values, SYSTOLIC_NORMAL_MIN, "less"
    )
    if is_sustained_sys_mild_low and avg_sys > SYSTOLIC_EXTREME_LOW:
        return {
            "severity": "mild",
            "vital": "blood_pressure",
            "description": f"mildly low systolic blood pressure (avg: {avg_sys:.0f} mmhg, {pct_sys_mild_low*100:.0f}% of readings < {SYSTOLIC_NORMAL_MIN} mmhg)"
        }

    # check mild diastolic abnormalities
    is_sustained_dia_mild_high, pct_dia_mild_high = _check_sustained_condition(
        diastolic_values, DIASTOLIC_NORMAL_MAX, "greater"
    )
    if is_sustained_dia_mild_high and avg_dia < DIASTOLIC_EXTREME_HIGH:
        return {
            "severity": "mild",
            "vital": "blood_pressure",
            "description": f"mildly elevated diastolic blood pressure (avg: {avg_dia:.0f} mmhg, {pct_dia_mild_high*100:.0f}% of readings > {DIASTOLIC_NORMAL_MAX} mmhg)"
        }

    is_sustained_dia_mild_low, pct_dia_mild_low = _check_sustained_condition(
        diastolic_values, DIASTOLIC_NORMAL_MIN, "less"
    )
    if is_sustained_dia_mild_low and avg_dia > DIASTOLIC_EXTREME_LOW:
        return {
            "severity": "mild",
            "vital": "blood_pressure",
            "description": f"mildly low diastolic blood pressure (avg: {avg_dia:.0f} mmhg, {pct_dia_mild_low*100:.0f}% of readings < {DIASTOLIC_NORMAL_MIN} mmhg)"
        }

    return None


def _analyze_respiratory_rate(vitals: List[Any]) -> Optional[Dict[str, Any]]:
    """
    analyze respiratory rate for abnormalities.

    args:
        vitals: list of vital records

    returns:
        dict with severity and description if abnormal, none otherwise
    """
    if not vitals:
        return None

    rr_values = [v.respiratory_rate for v in vitals]
    avg_rr = statistics.mean(rr_values)
    min_rr = min(rr_values)
    max_rr = max(rr_values)

    # check for extreme tachypnea
    is_sustained_high, pct_high = _check_sustained_condition(
        rr_values, RR_EXTREME_HIGH, "greater"
    )
    if is_sustained_high:
        return {
            "severity": "extreme",
            "vital": "respiratory_rate",
            "description": f"elevated respiratory rate detected (avg: {avg_rr:.1f} breaths/min, max: {max_rr:.1f} breaths/min, {pct_high*100:.0f}% of readings > {RR_EXTREME_HIGH} breaths/min)"
        }

    # check for extreme bradypnea
    is_sustained_low, pct_low = _check_sustained_condition(
        rr_values, RR_EXTREME_LOW, "less"
    )
    if is_sustained_low:
        return {
            "severity": "extreme",
            "vital": "respiratory_rate",
            "description": f"low respiratory rate detected (avg: {avg_rr:.1f} breaths/min, min: {min_rr:.1f} breaths/min, {pct_low*100:.0f}% of readings < {RR_EXTREME_LOW} breaths/min)"
        }

    # check for mild tachypnea
    is_sustained_mild_high, pct_mild_high = _check_sustained_condition(
        rr_values, RR_NORMAL_MAX, "greater"
    )
    if is_sustained_mild_high and avg_rr < RR_EXTREME_HIGH:
        return {
            "severity": "mild",
            "vital": "respiratory_rate",
            "description": f"mildly elevated respiratory rate (avg: {avg_rr:.1f} breaths/min, {pct_mild_high*100:.0f}% of readings > {RR_NORMAL_MAX} breaths/min)"
        }

    # check for mild bradypnea
    is_sustained_mild_low, pct_mild_low = _check_sustained_condition(
        rr_values, RR_NORMAL_MIN, "less"
    )
    if is_sustained_mild_low and avg_rr > RR_EXTREME_LOW:
        return {
            "severity": "mild",
            "vital": "respiratory_rate",
            "description": f"mildly low respiratory rate (avg: {avg_rr:.1f} breaths/min, {pct_mild_low*100:.0f}% of readings < {RR_NORMAL_MIN} breaths/min)"
        }

    return None


def _analyze_temperature(vitals: List[Any]) -> Optional[Dict[str, Any]]:
    """
    analyze body temperature for abnormalities.

    args:
        vitals: list of vital records

    returns:
        dict with severity and description if abnormal, none otherwise
    """
    if not vitals:
        return None

    temp_values = [v.body_temperature for v in vitals]
    avg_temp = statistics.mean(temp_values)
    min_temp = min(temp_values)
    max_temp = max(temp_values)

    # check for extreme fever
    is_sustained_high, pct_high = _check_sustained_condition(
        temp_values, TEMP_EXTREME_HIGH, "greater"
    )
    if is_sustained_high:
        return {
            "severity": "extreme",
            "vital": "temperature",
            "description": f"elevated body temperature detected (avg: {avg_temp:.1f}°c, max: {max_temp:.1f}°c, {pct_high*100:.0f}% of readings > {TEMP_EXTREME_HIGH}°c)"
        }

    # check for extreme hypothermia
    is_sustained_low, pct_low = _check_sustained_condition(
        temp_values, TEMP_EXTREME_LOW, "less"
    )
    if is_sustained_low:
        return {
            "severity": "extreme",
            "vital": "temperature",
            "description": f"low body temperature detected (avg: {avg_temp:.1f}°c, min: {min_temp:.1f}°c, {pct_low*100:.0f}% of readings < {TEMP_EXTREME_LOW}°c)"
        }

    # check for mild fever
    is_sustained_mild_high, pct_mild_high = _check_sustained_condition(
        temp_values, TEMP_NORMAL_MAX, "greater"
    )
    if is_sustained_mild_high and avg_temp < TEMP_EXTREME_HIGH:
        return {
            "severity": "mild",
            "vital": "temperature",
            "description": f"mildly elevated body temperature (avg: {avg_temp:.1f}°c, {pct_mild_high*100:.0f}% of readings > {TEMP_NORMAL_MAX}°c)"
        }

    # check for mild hypothermia
    is_sustained_mild_low, pct_mild_low = _check_sustained_condition(
        temp_values, TEMP_NORMAL_MIN, "less"
    )
    if is_sustained_mild_low and avg_temp > TEMP_EXTREME_LOW:
        return {
            "severity": "mild",
            "vital": "temperature",
            "description": f"mildly low body temperature (avg: {avg_temp:.1f}°c, {pct_mild_low*100:.0f}% of readings < {TEMP_NORMAL_MIN}°c)"
        }

    return None


def _aggregate_risk_level(signals: List[Dict[str, Any]]) -> str:
    """
    aggregate individual vital signals into overall risk level.

    rule: high if ANY vital shows extreme values;
          moderate if ANY shows mild abnormality;
          low otherwise

    args:
        signals: list of signal dicts with severity levels

    returns:
        "low", "moderate", or "high"
    """
    if not signals:
        return "low"

    # check for any extreme signals
    has_extreme = any(s["severity"] == "extreme" for s in signals)
    if has_extreme:
        return "high"

    # check for any mild signals
    has_mild = any(s["severity"] == "mild" for s in signals)
    if has_mild:
        return "moderate"

    return "low"


def _compute_vitals_summary(vitals: List[Any]) -> Dict[str, float]:
    """
    compute summary statistics for all vitals.

    args:
        vitals: list of vital records

    returns:
        dict with average values for each vital sign
    """
    if not vitals:
        return {}

    return {
        "heart_rate_avg": statistics.mean([v.heart_rate for v in vitals]),
        "heart_rate_min": min([v.heart_rate for v in vitals]),
        "heart_rate_max": max([v.heart_rate for v in vitals]),
        "spo2_avg": statistics.mean([v.spo2 for v in vitals]),
        "spo2_min": min([v.spo2 for v in vitals]),
        "spo2_max": max([v.spo2 for v in vitals]),
        "systolic_bp_avg": statistics.mean([v.systolic_bp for v in vitals]),
        "systolic_bp_min": min([v.systolic_bp for v in vitals]),
        "systolic_bp_max": max([v.systolic_bp for v in vitals]),
        "diastolic_bp_avg": statistics.mean([v.diastolic_bp for v in vitals]),
        "diastolic_bp_min": min([v.diastolic_bp for v in vitals]),
        "diastolic_bp_max": max([v.diastolic_bp for v in vitals]),
        "respiratory_rate_avg": statistics.mean([v.respiratory_rate for v in vitals]),
        "respiratory_rate_min": min([v.respiratory_rate for v in vitals]),
        "respiratory_rate_max": max([v.respiratory_rate for v in vitals]),
        "temperature_avg": statistics.mean([v.body_temperature for v in vitals]),
        "temperature_min": min([v.body_temperature for v in vitals]),
        "temperature_max": max([v.body_temperature for v in vitals]),
    }


def assess_risk(vitals: List[Any]) -> Dict[str, Any]:
    """
    assess risk level based on patient vitals over a time window.

    this function performs rule-based analysis of vital signs and returns
    a risk level with supporting signals. it does not provide medical
    diagnosis or treatment recommendations.

    args:
        vitals: list of vital model instances (e.g., last 2 hours of data)

    returns:
        dict containing:
            - risk_level: "low", "moderate", or "high"
            - signals: list of strings describing abnormal patterns
            - vitals_summary: dict with average/min/max for each vital
    """
    if not vitals:
        return {
            "risk_level": "low",
            "signals": [],
            "vitals_summary": {}
        }

    # analyze each vital sign
    signal_results = []

    hr_signal = _analyze_heart_rate(vitals)
    if hr_signal:
        signal_results.append(hr_signal)

    spo2_signal = _analyze_spo2(vitals)
    if spo2_signal:
        signal_results.append(spo2_signal)

    bp_signal = _analyze_blood_pressure(vitals)
    if bp_signal:
        signal_results.append(bp_signal)

    rr_signal = _analyze_respiratory_rate(vitals)
    if rr_signal:
        signal_results.append(rr_signal)

    temp_signal = _analyze_temperature(vitals)
    if temp_signal:
        signal_results.append(temp_signal)

    # aggregate risk level
    risk_level = _aggregate_risk_level(signal_results)

    # extract signal descriptions
    signals = [s["description"] for s in signal_results]

    # compute vitals summary
    vitals_summary = _compute_vitals_summary(vitals)

    return {
        "risk_level": risk_level,
        "signals": signals,
        "vitals_summary": vitals_summary
    }
