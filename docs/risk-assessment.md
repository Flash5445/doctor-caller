# risk assessment engine

## overview

the risk assessment engine provides rule-based analysis of patient vital signs to generate risk levels with supporting signals. this module does not provide medical diagnosis or treatment recommendations - it only performs data-driven analysis based on predefined thresholds.

**important disclaimers:**
- this is not a medical device
- does not provide diagnosis or treatment plans
- output should only be used to flag data patterns for review by medical professionals
- all thresholds are informational and not clinical guidelines

## architecture

### file location
- **implementation:** `backend/services/risk_engine.py`
- **tests:** `tests/test_risk_engine.py`
- **related:** `backend/models/vitals.py`, `backend/repositories/vitals_repository.py`

### main function

#### `assess_risk(vitals: List[Vital]) -> dict`

primary entry point for risk assessment.

**parameters:**
- `vitals`: list of vital model instances (typically last 2 hours of data)

**returns:**
```python
{
    "risk_level": "low" | "moderate" | "high",
    "signals": [
        "elevated heart rate detected (avg: 110 bpm, ...)",
        "low oxygen saturation (avg: 89%, ...)"
    ],
    "vitals_summary": {
        "heart_rate_avg": 110.5,
        "heart_rate_min": 95.0,
        "heart_rate_max": 125.0,
        # ... other vitals
    }
}
```

**workflow:**
1. analyze each vital sign individually using helper functions
2. collect all abnormal signals with severity levels
3. aggregate signals into overall risk level
4. compute summary statistics
5. return structured result

## threshold system

### two-tier threshold design

each vital sign has two threshold levels:
- **mild:** triggers "moderate" risk level
- **extreme:** triggers "high" risk level

this allows for graduated risk assessment based on severity.

### heart rate (bpm)

**normal range:** 60-100 bpm

**mild thresholds:**
- low: 50-60 bpm
- high: 100-120 bpm

**extreme thresholds:**
- low: <50 bpm (severe bradycardia)
- high: >120 bpm (severe tachycardia)

**conditions detected:**
- tachycardia (elevated heart rate)
- bradycardia (low heart rate)

### oxygen saturation (spo2 %)

**normal range:** ≥95%

**mild thresholds:**
- low: 92-95%

**extreme thresholds:**
- low: <92% (severe hypoxia)

**conditions detected:**
- hypoxia (low oxygen saturation)

### blood pressure (mmhg)

**systolic normal range:** 90-140 mmhg

**systolic mild thresholds:**
- low: 85-90 mmhg
- high: 140-160 mmhg

**systolic extreme thresholds:**
- low: <85 mmhg (severe hypotension)
- high: >160 mmhg (severe hypertension)

**diastolic normal range:** 60-90 mmhg

**diastolic mild thresholds:**
- low: 50-60 mmhg
- high: 90-100 mmhg

**diastolic extreme thresholds:**
- low: <50 mmhg
- high: >100 mmhg

**conditions detected:**
- hypertension (high blood pressure)
- hypotension (low blood pressure)

### respiratory rate (breaths/min)

**normal range:** 12-20 breaths/min

**mild thresholds:**
- low: 10-12 breaths/min
- high: 20-24 breaths/min

**extreme thresholds:**
- low: <10 breaths/min (severe bradypnea)
- high: >24 breaths/min (severe tachypnea)

**conditions detected:**
- tachypnea (rapid breathing)
- bradypnea (slow breathing)

### body temperature (°c)

**normal range:** 36.1-37.2°c

**mild thresholds:**
- low: 35.5-36.1°c
- high: 37.2-38.0°c

**extreme thresholds:**
- low: <35.5°c (hypothermia)
- high: >38.0°c (fever)

**conditions detected:**
- fever (elevated temperature)
- hypothermia (low temperature)

## sustained condition algorithm

### definition

a vital sign is considered "sustained abnormal" when **BOTH** conditions are met:

1. **average value exceeds threshold**
2. **at least 40% of readings exceed threshold**

this dual requirement prevents false positives from:
- brief spikes/dips in readings
- isolated measurement errors
- transient physiological variations

### implementation

```python
def _check_sustained_condition(
    values: List[float],
    threshold: float,
    comparison: str = "greater"
) -> tuple[bool, float]
```

**algorithm:**
1. calculate average of all values
2. count how many values exceed threshold
3. calculate percentage exceeding
4. check if average exceeds threshold AND percentage ≥ 40%

**example (tachycardia):**
```python
hr_values = [105, 110, 108, 112, 109, 111, 107, 110, 95, 98]
# average: 106.5 bpm (exceeds 100)
# 8 out of 10 exceed 100 (80% > 40%)
# result: sustained tachycardia detected
```

**example (non-sustained):**
```python
hr_values = [105, 95, 98, 92, 97, 110, 93, 94, 96, 108]
# average: 98.8 bpm (does not exceed 100)
# only 3 out of 10 exceed 100 (30% < 40%)
# result: not sustained, no signal generated
```

## vital sign analyzers

each vital sign has a dedicated analyzer function that returns `None` for normal values or a signal dict for abnormalities.

### signal structure

```python
{
    "severity": "mild" | "extreme",
    "vital": "heart_rate" | "spo2" | "blood_pressure" | "respiratory_rate" | "temperature",
    "description": "human-readable description with statistics"
}
```

### analyzer functions

#### `_analyze_heart_rate(vitals: List[Vital]) -> Optional[Dict]`

checks for tachycardia and bradycardia using sustained condition logic.

**priority:** checks extreme conditions first, then mild conditions.

**returns:** signal dict or none

#### `_analyze_spo2(vitals: List[Vital]) -> Optional[Dict]`

checks for hypoxia (low oxygen saturation).

**note:** only checks for low values, not high values (high spo2 is normal).

#### `_analyze_blood_pressure(vitals: List[Vital]) -> Optional[Dict]`

checks both systolic and diastolic pressure for hypertension and hypotension.

**priority:**
1. extreme systolic abnormalities
2. extreme diastolic abnormalities
3. mild systolic abnormalities
4. mild diastolic abnormalities

**returns:** first abnormality detected (most severe)

#### `_analyze_respiratory_rate(vitals: List[Vital]) -> Optional[Dict]`

checks for tachypnea (rapid breathing) and bradypnea (slow breathing).

#### `_analyze_temperature(vitals: List[Vital]) -> Optional[Dict]`

checks for fever and hypothermia.

## risk aggregation

### `_aggregate_risk_level(signals: List[Dict]) -> str`

combines individual vital signals into overall risk level using simple rule:

**algorithm:**
```
if any signal has severity == "extreme":
    return "high"
elif any signal has severity == "mild":
    return "moderate"
else:
    return "low"
```

**rationale:** conservative approach where ANY extreme abnormality warrants high risk, regardless of other vitals being normal.

### risk level meanings

**low:**
- all vitals within normal ranges
- no sustained abnormalities detected
- routine monitoring appropriate

**moderate:**
- one or more vitals show mild abnormalities
- sustained patterns of concern
- increased monitoring recommended

**high:**
- one or more vitals show extreme abnormalities
- significant deviations from normal ranges
- immediate medical review recommended

## vitals summary computation

### `_compute_vitals_summary(vitals: List[Vital]) -> Dict[str, float]`

calculates summary statistics for all vital signs:

**for each vital sign:**
- average (mean)
- minimum
- maximum

**output keys:**
- `heart_rate_avg`, `heart_rate_min`, `heart_rate_max`
- `spo2_avg`, `spo2_min`, `spo2_max`
- `systolic_bp_avg`, `systolic_bp_min`, `systolic_bp_max`
- `diastolic_bp_avg`, `diastolic_bp_min`, `diastolic_bp_max`
- `respiratory_rate_avg`, `respiratory_rate_min`, `respiratory_rate_max`
- `temperature_avg`, `temperature_min`, `temperature_max`

**usage:** provides quantitative context for the risk assessment and signals.

## usage examples

### basic usage

```python
from backend.config import get_db_session
from backend.repositories.vitals_repository import VitalsRepository
from backend.services.risk_engine import assess_risk

# get database session
session = get_db_session()
repo = VitalsRepository(session)

# fetch last 2 hours of vitals
vitals = repo.get_recent_vitals("PATIENT_001", window_hours=2)

# assess risk
result = assess_risk(vitals)

print(f"risk level: {result['risk_level']}")
print(f"signals: {result['signals']}")
print(f"average hr: {result['vitals_summary']['heart_rate_avg']:.1f}")
```

### example output (low risk)

```python
{
    "risk_level": "low",
    "signals": [],
    "vitals_summary": {
        "heart_rate_avg": 72.5,
        "heart_rate_min": 68.0,
        "heart_rate_max": 78.0,
        "spo2_avg": 97.8,
        # ...
    }
}
```

### example output (moderate risk)

```python
{
    "risk_level": "moderate",
    "signals": [
        "mildly elevated heart rate (avg: 110.5 bpm, 75% of readings > 100 bpm)"
    ],
    "vitals_summary": {
        "heart_rate_avg": 110.5,
        "heart_rate_min": 102.0,
        "heart_rate_max": 118.0,
        # ...
    }
}
```

### example output (high risk)

```python
{
    "risk_level": "high",
    "signals": [
        "elevated heart rate detected (avg: 135.2 bpm, max: 145.0 bpm, 90% of readings > 120 bpm)",
        "low oxygen saturation detected (avg: 88.5%, min: 85.0%, 85% of readings < 92%)"
    ],
    "vitals_summary": {
        "heart_rate_avg": 135.2,
        "spo2_avg": 88.5,
        # ...
    }
}
```

## testing

### test file
`tests/test_risk_engine.py`

### test coverage

**unit tests:**
1. `test_assess_risk_with_normal_vitals` - verifies low risk for normal values
2. `test_assess_risk_with_empty_vitals` - edge case handling
3. `test_assess_risk_with_extreme_tachycardia` - high hr detection
4. `test_assess_risk_with_mild_tachycardia` - moderate hr detection
5. `test_assess_risk_with_extreme_hypoxia` - low spo2 detection
6. `test_assess_risk_with_mild_hypoxia` - moderate spo2 detection
7. `test_assess_risk_with_extreme_hypertension` - high bp detection
8. `test_assess_risk_with_extreme_hypotension` - low bp detection
9. `test_assess_risk_with_extreme_fever` - fever detection
10. `test_assess_risk_with_extreme_tachypnea` - rapid breathing detection
11. `test_assess_risk_with_multiple_mild_abnormalities` - multiple signals
12. `test_check_sustained_condition_with_sustained_high` - sustained logic
13. `test_check_sustained_condition_with_non_sustained` - non-sustained detection
14. `test_check_sustained_condition_with_sustained_low` - sustained low logic
15. `test_aggregate_risk_level_with_extreme_signal` - aggregation logic
16. `test_aggregate_risk_level_with_only_mild` - mild aggregation
17. `test_aggregate_risk_level_with_no_signals` - empty signals
18. `test_analyze_heart_rate_returns_none_for_normal` - analyzer normal case
19. `test_analyze_spo2_returns_signal_for_low` - analyzer abnormal case
20. `test_analyze_blood_pressure_returns_signal_for_hypertension` - bp analyzer
21. `test_assess_risk_with_real_deteriorating_data` - integration test

**integration test:**
- uses real synthetic deteriorating vitals from database
- verifies that deteriorating trend produces moderate or high risk
- validates full end-to-end workflow

### running tests

```bash
.venv/bin/pytest tests/test_risk_engine.py -v
```

**expected result:** 21 tests passed

## performance characteristics

### time complexity

- **assess_risk:** o(n) where n = number of vital records
  - each analyzer: o(n) - single pass through vitals
  - total: 5 analyzers × o(n) = o(n)

- **sustained condition check:** o(n)
  - mean calculation: o(n)
  - count exceeding: o(n)
  - total: o(n)

### typical usage

**input:** 120 vital records (2 hours at 1-minute intervals)

**processing time:** <10ms on modern hardware

**memory:** minimal - no data duplication, streaming calculations

## integration points

### upstream dependencies

**vitals repository** (`backend/repositories/vitals_repository.py`)
- provides vital records via `get_recent_vitals()`
- supplies input data for risk assessment

**vitals model** (`backend/models/vitals.py`)
- defines vital record structure
- accessed via dot notation (e.g., `vital.heart_rate`)

### downstream consumers

**summary service** (step 3, future)
- will use risk assessment result as input for claude summarization
- passes risk level and signals to llm for context

**call service** (step 5, future)
- will include risk level in phone call script
- uses signals to inform doctor of concerning patterns

**api endpoints** (step 4, future)
- will expose risk assessment via rest api
- returns risk result as json response

## configuration

### adjusting thresholds

thresholds are defined as module-level constants at top of `risk_engine.py`:

```python
# heart rate thresholds (bpm)
HR_NORMAL_MIN = 60
HR_NORMAL_MAX = 100
HR_MILD_LOW = 50
HR_MILD_HIGH = 120
HR_EXTREME_LOW = 50
HR_EXTREME_HIGH = 120
```

**to modify:**
1. edit constant values in `risk_engine.py`
2. run tests to verify changes: `.venv/bin/pytest tests/test_risk_engine.py -v`
3. update this documentation with new threshold values

### adjusting sustained percentage

sustained condition requires 40% of readings to exceed threshold:

```python
SUSTAINED_THRESHOLD_PCT = 0.4
```

**to make more sensitive:** decrease to 0.3 (30%)

**to make less sensitive:** increase to 0.5 (50%)

## limitations and considerations

### not a medical device

- does not diagnose medical conditions
- does not recommend treatments
- thresholds are informational, not clinical standards
- output requires review by qualified medical professionals

### data quality assumptions

- assumes vitals are accurate and properly calibrated
- does not detect sensor failures or invalid readings
- relies on upstream data validation

### temporal considerations

- designed for 2-hour time windows
- may not detect long-term trends (days/weeks)
- does not account for circadian rhythms or context (sleep, exercise, etc.)

### threshold limitations

- uses fixed thresholds, not personalized to patient baseline
- does not account for age, medications, or medical history
- some patients may have different "normal" ranges

### scope

**currently analyzes:**
- heart rate, spo2, blood pressure, respiratory rate, temperature

**does not analyze:**
- trends over time (e.g., "rapidly increasing")
- derived metrics (pulse pressure, map) - though calculated in vitals
- combinations of vitals (e.g., shock index)
- rate of change

## future enhancements

### potential improvements

1. **personalized baselines**
   - store patient's historical normal ranges
   - flag deviations from personal baseline, not just population norms

2. **trend analysis**
   - detect rapid deterioration (e.g., hr increasing >10 bpm/hour)
   - identify improving vs worsening patterns

3. **multi-variate analysis**
   - combine vitals (e.g., low bp + high hr = potential shock)
   - calculate derived indicators (shock index, modified early warning score)

4. **temporal context**
   - account for time of day, activity level
   - adjust thresholds based on patient state (sleeping, post-exercise, etc.)

5. **machine learning integration**
   - replace rule-based thresholds with learned patterns
   - predict deterioration risk before vitals become critical

6. **confidence scores**
   - add uncertainty estimates to risk assessments
   - flag low-confidence assessments (sparse data, noisy readings)

7. **llm-based inference** (step 2 requirement)
   - pass vitals summary and signals to claude
   - let llm provide additional context-aware risk assessment
   - combine rule-based + llm-based analysis

## related files

- `backend/services/risk_engine.py` - implementation
- `tests/test_risk_engine.py` - test suite
- `backend/models/vitals.py` - data model
- `backend/repositories/vitals_repository.py` - data access
- `docs/vitals-ingestion.md` - upstream data documentation

## version history

### v1.0 (current)
- initial implementation
- rule-based risk assessment
- five vital signs analyzed
- two-tier threshold system
- sustained condition detection
- comprehensive test coverage

## contact and support

for questions about risk assessment logic or thresholds, consult with medical professionals. this is engineering documentation, not clinical guidance.
