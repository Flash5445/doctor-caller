# vitals summarization service

## overview

the vitals summarization service uses anthropic's claude ai to generate concise, clinically-relevant summaries of patient vital signs data for delivery to medical providers via phone calls.

**critical constraints:**
- does not provide medical diagnosis or treatment recommendations
- only summarizes data and highlights concerning trends
- uses neutral, objective language appropriate for healthcare professionals
- all output must pass validation to ensure safety and compliance

## architecture

### file locations
- **implementation:** `backend/services/summary_service.py`
- **tests:** `tests/test_summary_service.py`
- **dependencies:** anthropic sdk, vitals repository, risk engine

### main function

#### `generate_vitals_summary(patient_id, vitals, risk_assessment, patient_context=None) -> dict`

orchestrates the full summary generation workflow.

**parameters:**
- `patient_id` (str): patient identifier (e.g., "PATIENT_001")
- `vitals` (List[Vital]): list of vital records from repository
- `risk_assessment` (dict): output from assess_risk() containing risk_level and signals
- `patient_context` (Optional[dict]): additional metadata (unused in mvp)

**returns:**
```python
{
    "summary_text": "Patient PATIENT_001 vital signs...",
    "word_count": 187,
    "generated_at": "2025-11-14T17:30:00Z",
    "model_used": "claude-3-5-haiku-20241022",
    "prompt_tokens": 450,
    "completion_tokens": 200
}
```

**workflow:**
1. validate inputs (patient_id, vitals, risk_assessment)
2. format vitals data for prompt
3. build system and user prompts
4. call claude api with retry logic
5. validate generated summary
6. return structured result with metadata

**raises:**
- `InvalidInputError`: invalid or missing inputs
- `APIError`: claude api call failure
- `ValidationError`: generated summary fails validation

---

## component functions

### 1. format_vitals_for_prompt

```python
format_vitals_for_prompt(vitals: List[Vital], risk_assessment: dict) -> dict
```

extracts statistics and detects trends from vitals data.

**trend detection algorithm:**
- compares first 25% vs last 25% of readings
- key vitals analyzed: heart rate, spo2, systolic bp

**trend classification:**
- **deteriorating:** hr up >10 bpm OR spo2 down >2% OR systolic up >10 mmhg
- **improving:** hr down >10 bpm OR spo2 up >2% OR systolic down >10 mmhg
- **stable:** otherwise

**output includes:**
- time window (start_time, end_time)
- reading count
- avg/min/max for all 5 vital signs
- trend ("deteriorating", "stable", "improving")
- patient context (age, gender)
- risk level and signals

### 2. build_summary_prompt

```python
build_summary_prompt(patient_id: str, vitals_data: dict) -> tuple[str, str]
```

constructs carefully engineered prompts for claude.

**returns:** `(system_prompt, user_prompt)`

**system prompt key elements:**
- role definition: "medical data summarization assistant"
- explicit constraints: no diagnosis, no treatment recommendations
- output requirements: max 200 words, 2-3 paragraphs, professional terminology
- target audience: healthcare professionals receiving phone call

**user prompt structure:**
- patient id and time window
- vital signs summary (all 5 vitals with avg/min/max)
- overall trend
- risk assessment level
- concerning patterns (if any)
- patient demographics

### 3. call_claude_api

```python
call_claude_api(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 300,
    temperature: float = 0.3
) -> dict
```

makes http call to anthropic with retry logic.

**model:** claude-3-5-haiku-20241022 (fast, cost-effective)

**parameters:**
- `max_tokens`: 300 (sufficient for ~200 word summary)
- `temperature`: 0.3 (deterministic, factual output)

**retry logic:**
- max attempts: 3
- backoff factor: 2.0 (exponential)
- retry on: 429 (rate limit), 500 (server error), timeout
- no retry on: 401 (auth error), 400 (bad request)

**error handling:**
- missing api key → ValueError
- auth failure → APIError (no retry)
- transient errors → retry with backoff
- all retries failed → APIError

### 4. validate_summary

```python
validate_summary(summary_text: str, patient_id: str) -> tuple[bool, Optional[str]]
```

ensures generated summary meets safety and quality requirements.

**validation checks:**

1. **length:** 50-250 words (buffer around 200 target)
2. **patient id:** must reference patient identifier
3. **time reference:** must mention time window/period/hours
4. **risk reference:** must mention risk assessment/level
5. **strict diagnosis patterns:** reject if contains:
   - "diagnosed with"
   - "diagnosis of"
   - "patient has"
   - "patient is suffering"
   - "condition is"
6. **strict treatment patterns:** reject if contains:
   - "recommend treatment"
   - "prescribe"
   - "administer"
   - "should be given"
   - "requires medication"

**validation philosophy:**
- relaxed approach: allows medical terms in neutral context
- e.g., "data shows elevated readings" is allowed
- but "patient is diagnosed with tachycardia" is rejected

**returns:** `(is_valid, error_message)` or `(True, None)` if valid

---

## custom exceptions

### exception hierarchy

```python
SummaryServiceError (base)
├── InvalidInputError (invalid/missing inputs)
├── APIError (claude api failures)
└── ValidationError (summary fails validation)
```

**usage:**
```python
try:
    result = generate_vitals_summary(patient_id, vitals, risk)
except InvalidInputError as e:
    # handle missing/invalid inputs
except APIError as e:
    # handle api failures (retry exhausted, auth error, etc.)
except ValidationError as e:
    # handle generated summary that failed validation
```

---

## prompt engineering

### system prompt

```
you are a medical data summarization assistant for an automated patient monitoring system.

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
- suitable for text-to-speech phone delivery
```

### user prompt template

```
generate a summary for patient {patient_id} based on the following data:

time window: last 2 hours ({start_time} to {end_time})
total readings: {num_readings}

vital signs summary:
- heart rate: avg {hr_avg} bpm (range: {hr_min}-{hr_max})
- oxygen saturation: avg {spo2_avg}% (range: {spo2_min}-{spo2_max}%)
- blood pressure: avg {systolic}/{diastolic} mmhg
- respiratory rate: avg {rr_avg} breaths/min
- temperature: avg {temp_avg}°c

overall trend: {trend}
risk assessment: {risk_level}
[concerning patterns if any]

patient context: {age} year old {gender}

generate a concise summary (max 200 words) suitable for a phone call to a healthcare provider.
```

### design principles

1. **clear role definition:** summarization assistant, not medical advisor
2. **explicit constraints:** list prohibited actions
3. **structured input:** consistent formatting for vitals
4. **specific output requirements:** length, format, tone
5. **low temperature:** factual, deterministic output
6. **phone-optimized:** prose format for natural text-to-speech

---

## configuration

### environment variables

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx...  # required
```

### constants (in code)

```python
MAX_SUMMARY_WORDS = 200
MIN_SUMMARY_WORDS = 50
MAX_SUMMARY_WORDS_BUFFER = 250
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 300
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2.0
MODEL_NAME = "claude-3-5-haiku-20241022"
```

**rationale for haiku model:**
- faster response times (1-2 seconds vs 3-5 for sonnet)
- lower cost ($0.25/million input tokens vs $3/million)
- sufficient quality for structured summarization tasks
- appropriate for production scaling

---

## usage examples

### basic usage

```python
from backend.config import get_db_session
from backend.repositories.vitals_repository import VitalsRepository
from backend.services.risk_engine import assess_risk
from backend.services.summary_service import generate_vitals_summary

# setup
session = get_db_session()
repo = VitalsRepository(session)

# fetch data
vitals = repo.get_recent_vitals("PATIENT_001", window_hours=2)
risk = assess_risk(vitals)

# generate summary
result = generate_vitals_summary("PATIENT_001", vitals, risk)

print(f"summary: {result['summary_text']}")
print(f"word count: {result['word_count']}")
print(f"tokens: {result['prompt_tokens']} in, {result['completion_tokens']} out")
```

### example output: low risk

**input:**
- 120 vitals over 2 hours
- all normal ranges
- risk: low, no signals

**generated summary:**
```
Patient PATIENT_001 vital signs from 15:30 to 17:30 show stable measurements
over the two hour monitoring period. Heart rate averaged 72 bpm with range
68-78 bpm, oxygen saturation maintained at 98% throughout, blood pressure
steady at 120/80 mmHg, respiratory rate 16 breaths per minute, temperature
36.8°C. Risk assessment: low. All vitals remained within normal ranges
demonstrating good physiological stability.
```

**metadata:**
- word_count: 67
- model: claude-3-5-haiku-20241022
- prompt_tokens: 420
- completion_tokens: 75

### example output: high risk

**input:**
- 120 vitals over 2 hours
- deteriorating trend
- risk: high, signals for tachycardia and hypoxia

**generated summary:**
```
Patient PATIENT_001 vital signs from 15:30 to 17:30 show deteriorating trend
with multiple concerning patterns. Heart rate increased from average 65 bpm
initially to 125 bpm in final readings, with 85% of recent readings exceeding
100 bpm. Oxygen saturation declined from 96% to 89% with minimum recorded at
85%. Blood pressure elevated from 118/76 to 138/88 mmHg. Respiratory rate and
temperature showed mild increases. Risk assessment: high. Data indicates
sustained tachycardia and hypoxia with progressive physiological stress
requiring immediate medical review.
```

**metadata:**
- word_count: 98
- model: claude-3-5-haiku-20241022
- prompt_tokens: 510
- completion_tokens: 110

---

## testing

### test file
`tests/test_summary_service.py`

### test coverage (19 tests)

**unit tests (14):**
1. format_vitals detects normal/stable vitals
2. format_vitals detects deteriorating trend
3. format_vitals detects improving trend
4. format_vitals raises on empty input
5. build_prompt has correct structure
6. build_prompt includes signals when present
7. validate accepts valid summary
8. validate rejects too short (<50 words)
9. validate rejects too long (>250 words)
10. validate rejects diagnostic language
11. validate rejects treatment recommendations
12. validate requires patient id reference
13. validate requires time reference
14. validate requires risk reference

**integration tests with mocked api (3):**
15. call_claude_api success (mocked)
16. call_claude_api missing key error
17. generate_vitals_summary validates inputs

**end-to-end tests (2):**
18. generate summary with normal vitals (mocked api)
19. generate summary with high risk vitals (mocked api)

### running tests

```bash
.venv/bin/pytest tests/test_summary_service.py -v
```

**expected result:** 19 passed

### mocking strategy

- all tests mock anthropic api (no real api calls in tests)
- use `unittest.mock` to mock api responses
- realistic synthetic responses for validation
- test error conditions (rate limits, auth failures, etc.)

---

## performance

### latency

**typical workflow:**
- format vitals: <5ms
- build prompts: <5ms
- claude api call: 1-2 seconds (haiku model)
- validate summary: <5ms
- **total: ~1-2 seconds**

### cost

**anthropic haiku pricing:**
- input: $0.25 per million tokens
- output: $1.25 per million tokens

**per summary:**
- input: ~500 tokens × $0.25/1M = $0.000125
- output: ~200 tokens × $1.25/1M = $0.000250
- **total: ~$0.000375 per summary**

**at scale:**
- 1,000 calls/day = $0.38/day = $11.40/month
- 10,000 calls/day = $3.75/day = $112.50/month

**comparison to sonnet:**
- sonnet: ~$0.0045 per summary (12x more expensive)
- haiku: adequate quality for this structured task
- cost savings: significant at scale

### optimization opportunities

1. **caching:** cache summaries for 5 minutes (reduce duplicate calls)
2. **batch processing:** if generating multiple summaries, batch api calls
3. **model selection:** use haiku by default, sonnet only if needed
4. **prompt optimization:** reduce prompt length without losing quality

---

## integration points

### upstream dependencies

**from step 1 (vitals repository):**
```python
vitals = repo.get_recent_vitals(patient_id, window_hours=2)
```

**from step 2 (risk engine):**
```python
risk = assess_risk(vitals)
```

### downstream consumers

**to step 5 (twilio call service - future):**
```python
summary = generate_vitals_summary(patient_id, vitals, risk)
call_service.start_call(summary["summary_text"])
```

**to step 4 (api endpoints - future):**
```python
# POST /call-doctor endpoint
summary_result = generate_vitals_summary(...)
return {
    "summary": summary_result["summary_text"],
    "word_count": summary_result["word_count"]
}
```

---

## limitations and considerations

### not a medical device

- does not diagnose conditions
- does not recommend treatments
- output requires review by licensed professionals
- llm-generated content may vary

### data quality assumptions

- assumes vitals are accurate and calibrated
- does not detect sensor failures
- relies on upstream validation

### llm variability

- temperature=0.3 for consistency but not 100% deterministic
- same inputs may produce slightly different summaries
- validation ensures minimum quality standards

### validation strictness

- relaxed validation allows neutral medical terminology
- strict patterns rejected (diagnosis, treatment)
- balance between safety and natural language

### scope

**currently summarizes:**
- 5 vital signs (hr, spo2, bp, rr, temp)
- risk level and signals
- overall trend
- basic patient demographics

**does not include:**
- medical history
- medications
- prior diagnoses
- detailed clinical context

---

## future enhancements

### potential improvements

1. **personalized context**
   - include patient's baseline vitals
   - reference medical history
   - mention current medications

2. **multi-language support**
   - generate summaries in different languages
   - especially spanish for broader accessibility

3. **longer time windows**
   - support 6-hour, 12-hour, 24-hour summaries
   - detect longer-term trends

4. **adaptive prompting**
   - adjust prompt based on risk level
   - more detail for high-risk cases
   - briefer for low-risk

5. **confidence scoring**
   - llm returns confidence in summary
   - flag uncertain or ambiguous cases

6. **structured output**
   - json format for programmatic parsing
   - separate sections: overview, vitals, concerns

7. **cost optimization**
   - cache for duplicate queries
   - dynamic model selection (haiku vs sonnet)
   - prompt compression

---

## related files

- `backend/services/summary_service.py` - implementation
- `tests/test_summary_service.py` - test suite
- `backend/services/risk_engine.py` - risk assessment (upstream)
- `backend/repositories/vitals_repository.py` - data access (upstream)
- `backend/models/vitals.py` - data model
- `docs/risk-assessment.md` - risk engine documentation
- `docs/vitals-ingestion.md` - vitals repository documentation

---

## version history

### v1.0 (current)
- initial implementation with claude haiku
- prose format for tts delivery
- relaxed validation approach
- first 25% vs last 25% trend detection
- no caching (mvp)
- comprehensive test coverage (19 tests)

---

## troubleshooting

### common issues

**issue:** "ANTHROPIC_API_KEY environment variable not set"
**solution:** add api key to `.env` file or export in shell

**issue:** "generated summary failed validation: summary too short"
**solution:** llm response <50 words - check prompt, increase max_tokens, or adjust validation

**issue:** "claude api call failed: authentication failed"
**solution:** verify api key is correct and active

**issue:** "generated summary failed validation: contains diagnostic language"
**solution:** llm used prohibited phrases - review system prompt, may need to regenerate

---

## safety and compliance

### disclaimers

- all summaries prefaced with "this is an automated summary call"
- phone script includes "not a diagnosis or treatment recommendation"
- output validated for prohibited medical language
- designed for data delivery, not medical decision-making

### privacy considerations

- patient id used (non-phi in mvp with synthetic data)
- for real deployment: ensure hipaa compliance
- api calls to anthropic: review data processing agreement
- consider on-premise llm deployment for maximum privacy

### audit trail

- all summaries logged with metadata (timestamps, tokens, model)
- risk assessment results stored with summary
- full vitals data retained for review

---

## contact and support

for questions about summarization service or claude integration, consult engineering documentation. this is a technical tool for data summarization, not clinical guidance.
