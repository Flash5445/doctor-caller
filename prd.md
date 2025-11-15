## 1. Abstract

**Product Name (working):** AI Doctor Call Agent (AIDCA)

**Goal (UN SDG #3 – Good Health and Well-being)**
Build an application that, at the press of a button, does the following:

1. **Ingests time-series patient vitals** (from a Kaggle dataset in the MVP; from real devices later).
2. **Pulls the last 2 hours of vitals** for a target patient.
3. **Generates a concise, clinically relevant summary** and risk flag using an LLM (Claude).
4. **Places an outbound phone call via Twilio** to a configured doctor/hospital phone number.
5. **Delivers the vitals summary + context via voice** and (optionally) collects advice or callback instructions from the provider.

**Critical constraints & safety:**

* App **never provides a diagnosis or treatment plan**; it only summarizes data and connects to real medical professionals.
* All messaging must include **clear disclaimers**: “Not a medical device” / “Not a substitute for professional care.”
* For real deployments (beyond Kaggle demo), system must be designed with **HIPAA-/PHI-style privacy** in mind (encryption, consent, audit logs).

---

## 2. Proposed Tech Stack

### 2.1 Core Application

* **Backend**
  
  * Language: **Python 3.x**
  * Framework: **Flask**

* **Frontend**
  
  * Framework: **React** or **Next.js**
  * UI Components: Material UI / Chakra UI (your choice)
  * Platform: Web app (MVP) with one main user action: **“Call Doctor Now”** button.

### 2.2 External Services

* **LLM Engine**
  
  * **Anthropic Claude API**
    
    * Text completions (for generating summaries, call scripts, follow-up prompts).

* **Telephony**
  
  * **Twilio Programmable Voice**
    
    * Outbound calls
    * TwiML for TTS prompts
    * (Stretch) Twilio Media Streams for real-time speech-to-text/LLM integration.

* **Speech & Transcription**
  
  * Twilio’s native TTS
  * For transcription (if doing two-way calls): Twilio + a speech-to-text service (or Claude if you later add voice support).

## 3. Data Model (MVP)

### 3.1 Vitals Table (from Kaggle)

**Table: `vitals`**

* `id` (PK)
* `patient_id` (string/UUID)
* `timestamp` (UTC datetime)
* `heart_rate` (int / float)
* `blood_pressure_systolic` (int)
* `blood_pressure_diastolic` (int)
* `respiratory_rate` (int / float)
* `spo2` (float)
* `temperature` (float)
* Additional fields as available in the Kaggle dataset.

**Query pattern for “last 2 hours”:**

```sql
SELECT *
FROM vitals
WHERE patient_id = :patient_id
  AND timestamp >= (NOW() - INTERVAL '2 hours')
ORDER BY timestamp ASC;
```

The backend encapsulates this in a `VitalsRepository` class.

---

## 4. Implementation Protocol (Step-by-Step)

Each step has: **Goal, Tasks**, and an example **Prompt for an Agentic Coding Assistant**.

### Step 0 – Project Scaffolding

**Goal:** Basic repo setup for backend, frontend, and shared config.

**Tasks:**

1. Initialize a monorepo (or two repos) with:
   
   * `/backend` (Flask)
   * `/frontend` (React/Next.js)

2. Add Dockerfiles and docker-compose for Postgres + app.

3. Configure `.env` for:
   
   * `ANTHROPIC_API_KEY`
   * `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
   * `TWILIO_CALLER_ID` (verified Twilio number)
   * `PROVIDER_PHONE_NUMBER` (target hospital/doctor)

4. Lint & formatting: `black`, `ruff` for Python; `eslint`, `prettier` for JS/TS.

**Prompt for Agent (Step 0):**

> You are a senior full-stack engineer.
> Create a monorepo with `/backend` using FastAPI (Python) and `/frontend` using Next.js (TypeScript).
> Configure environment variables for Anthropic and Twilio API keys and for a provider phone number.
> Include basic README instructions to run the app locally.

---

### Step 1 – Data Ingestion & Vitals Repository

**Goal:** Load Kaggle time-series vitals into a local Postgres DB with a clean repository interface.

**Tasks:**

1. Write a one-off **ingestion script** (`scripts/ingest_kaggle_vitals.py`) that:
   
   * Reads Kaggle CSV (file path configurable).
   * Normalizes columns to match `vitals` schema.

2. Implement `VitalsRepository` with methods:
   
   * `get_recent_vitals(patient_id: str, window_hours: int = 2)`
   * `get_latest_vitals(patient_id: str)`

3. Add unit tests for the repository (mock DB or test DB).

**Prompt for Agent (Step 1):**

> You are a Python backend engineer.
> In the `/backend` folder, implement a `vitals` module that contains:
> 
> * A SQLAlchemy model for a `vitals` table with fields: id, patient_id, timestamp, heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2, temperature.
> * A `VitalsRepository` class with methods `get_recent_vitals(patient_id: str, window_hours: int = 2)` and `get_latest_vitals(patient_id: str)`, using Postgres.
>   Also create a `scripts/ingest_kaggle_vitals.py` file that reads a Kaggle CSV, normalizes columns to the model, and bulk-inserts into the table.

---

### Step 2 – Risk Assessment & Feature Engineering (Simple Rule-Based MVP)

**Goal:** Provide a basic triage/risk flag (e.g., Normal / Elevated / Critical) using simple rule-based thresholds (not medical advice, just a data flag).

**Tasks:**

1. Implement a **rule-based scoring** module (e.g., `risk_engine.py`) that:
   
   * Examines last 2 hours of vitals.
   
   * Computes simple flags like:
     
     * Tachycardia if heart_rate > 100 for sustained periods.
     * Hypotension if systolic < 90.
     * Hypoxia if SpO2 < 92.
   
   * Returns:
     
     * `risk_level` (string: `"low" | "moderate" | "high"`)
     * `supporting_signals` (list of strings describing abnormal patterns)

2. Ensure **no diagnostic claims** in code or user-facing text: purely “risk level based on thresholds”.

**Prompt for Agent (Step 2):**

> In `/backend`, create a `risk_engine.py` module with a function `assess_risk(vitals: List[VitalRecord]) -> dict`.
> The function should compute a `risk_level` ("low", "moderate", "high") and a list of `signals` based on simple thresholds:
> 
> * heart_rate > 110 -> increased risk signal
> * systolic < 90 or diastolic < 60 -> low blood pressure signal
> * spo2 < 92 -> low oxygen signal
>   If multiple signals are present or values are extreme (e.g., HR > 130, SpO2 < 88), set `risk_level` to "high".
>   Make sure the function does not make medical diagnoses, only returns a qualitative risk label and text descriptions of abnormal values.

---

### Step 3 – Vitals Summary Generator (Claude Prompting)

**Goal:** Use Claude to generate a concise, provider-ready summary of last 2 hours of vitals + risk info.

**Tasks:**

1. Implement `summary_service.py` with:
   
   * `build_summary_prompt(vitals, risk_assessment, patient_context)`
   * `generate_vitals_summary(...)` which calls Claude and returns a short text (e.g., 2–3 paragraphs).

2. Include disclaimers in the prompt: LLM is assisting with summarization, not diagnosing.

3. Format the summary to include:
   
   * Patient identifier (non-PII label for MVP).
   * Time window.
   * Key trends.
   * Risk level and signals.

**Example prompt template (backend):**

> System:
> You are a medical note summarization assistant. You are not a doctor and must not provide diagnoses or treatment plans. You only summarize the provided vital signs and highlight concerning trends using neutral language.
> 
> User:
> Here is time-series vital data for a patient over the last 2 hours:
> {{STRUCTURED_VITALS_JSON}}
> Risk assessment: {{RISK_LEVEL}} with signals: {{SIGNALS}}
> Generate a short summary (max 200 words) for a nurse or doctor who will receive a phone call.
> 
> * Mention the time window and general trend (stable, improving, worsening).
> * Mention any abnormal values neutrally.
> * Avoid diagnosis or treatment advice.

**Prompt for Agent (Step 3):**

> In `/backend`, implement a `summary_service.py` file.
> Create a function `generate_vitals_summary(patient_id: str, vitals: List[VitalRecord], risk: dict) -> str` that:
> 
> * Constructs a prompt for Anthropic Claude using the rules above.
> * Calls Claude via HTTP using `ANTHROPIC_API_KEY`.
> * Returns a short textual summary suitable for a clinician, max 200 words.
>   Include a system prompt that clearly forbids making diagnoses or recommending treatment.

---

### Step 4 – Backend API Endpoints

**Goal:** Expose a clean API for the frontend and orchestration.

**Endpoints (MVP):**

1. `GET /patients/{patient_id}/vitals/recent?hours=2`
   
   * Returns recent vitals JSON.

2. `POST /call-doctor`
   
   * Body: `{ "patient_id": "string" }`
   
   * Triggers the full workflow:
     
     1. Fetch last 2 hours of vitals.
     2. Run risk assessment.
     3. Generate summary via Claude.
     4. Initiate Twilio call with summary script.

3. `GET /calls/{call_id}/status`
   
   * Returns Twilio call status.

**Prompt for Agent (Step 4):**

> In `/backend`, create Flask API endpoints:
> 
> * `GET /patients/{patient_id}/vitals/recent` returning the last N hours of vitals.
> 
> * `POST /call-doctor` which:
>   
>   * Reads `patient_id` from the body.
>   * Uses `VitalsRepository` to fetch last 2 hours of vitals.
>   * Uses `assess_risk` to compute risk.
>   * Uses `generate_vitals_summary` to create a text summary.
>   * Calls a `call_service.start_call(summary_text)` function to initiate a Twilio call.
>     Return a JSON response containing `call_id` and a human-readable message.

---

### Step 5 – Twilio Call Service

**Goal:** Implement Twilio integration that reads the summary over the phone to the provider.

**Tasks:**

1. Implement `call_service.py` with:
   
   * `start_call(summary_text: str) -> str` (returns Twilio `call_sid`).

2. Flow:
   
   * `start_call`:
     
     * Calls Twilio’s Programmable Voice API to dial `PROVIDER_PHONE_NUMBER`.
     * Provides a webhook URL (e.g., `/twilio/voice`) that returns TwiML.

3. Implement `/twilio/voice` endpoint:
   
   * Responds with TwiML `<Say>` (or `<Play>` if you generate an audio file) reading:
     
     * Short intro: “This is an automated summary call; not a diagnosis.”
     * Patient/ID + summary text.
     * Optional: ask provider to press a key to confirm receipt (DTMF collection).

**Example TwiML (conceptual):**

```xml
<Response>
  <Say voice="Polly.Joanna">
    Hello. This is an automated summary call from the AI Doctor Call Agent.
    This is not a diagnosis or treatment recommendation.
  </Say>
  <Pause length="1"/>
  <Say>
    {{SUMMARY_TEXT}}
  </Say>
</Response>
```

**Prompt for Agent (Step 5):**

> In `/backend`, implement `call_service.py` that uses the Twilio Python SDK.
> Create a `start_call(summary_text: str) -> str` function that:
> 
> * Starts an outbound call from `TWILIO_CALLER_ID` to `PROVIDER_PHONE_NUMBER`.
> * Sets the call’s `url` to a FastAPI route `/twilio/voice?call_id={call_id}` which returns TwiML using the provided summary_text.
>   Also implement the `/twilio/voice` route that returns TwiML to read a disclaimer and then the summary text via `<Say>`.

---

### Step 6 – Interactive Call Mode with Claude

**Goal:** Enable two-way calls where Claude helps ask/answer structured questions (still not diagnosing).

**High-level tasks:**

* Use **Twilio Media Streams** to stream audio to a transcription service.

* Pass live transcript to Claude; have it:
  
  * Extract structured “doctor advice” text.
  * Confirm disclaimers.

* Store doctor’s advice as a note in DB.

---

### Step 7 – Frontend: “Call Doctor” Flow

**Goal:** Simple UI that triggers backend call and shows status.

**Tasks:**

1. Build a simple dashboard page with:
   
   * Patient selector (dropdown or pre-configured patient_id for MVP).
   * “Last 2 hours vitals” mini-chart (optional) using an API call.
   * **Primary button:** “Call Doctor Now.”

2. When button is clicked:
   
   * Call `POST /call-doctor` with `patient_id`.
   * Show loading state, then show success or error with the `call_id`.

3. Optionally:
   
   * Poll `GET /calls/{call_id}/status` to show live Twilio status (ringing, in-progress, completed).

**Prompt for Agent (Step 7):**

> In `/frontend`, create a Next.js page `/dashboard` with:
> 
> * A dropdown to select a `patient_id` (hard-code a few IDs for the Kaggle data).
> * A "Call Doctor Now" button.
>   When clicked, it should:
> * Call `POST /call-doctor` on the backend with the selected patient_id.
> * Display the response (whether the call was initiated and the returned `call_id`).
>   Add a basic success/error toast or banner.

---

### Step 8 – Logging, Monitoring, and Safety

**Goal:** Ensure we have traceability and safety hooks.

**Tasks:**

1. Create a `CallLog` table:
   
   * `call_id`, `patient_id`, `timestamp`, `risk_level`, `summary_snippet`, `twilio_sid`, `status`.

2. Store:
   
   * Prompt and response hashes (not full PHI if using real data in future).

3. Add:
   
   * Basic error handling in all endpoints (especially Twilio and Claude calls).
   * Rate limiting / simple throttling for call operations.

**Prompt for Agent (Step 8):**

> In `/backend`, add a `CallLog` SQLAlchemy model with fields: id, patient_id, created_at, risk_level, summary_preview (first 200 chars), twilio_sid, status.
> Modify `POST /call-doctor` so that it creates a `CallLog` entry when a call is initiated and updates `status` and `twilio_sid` as the Twilio call progresses.
> Add basic exception handling so that errors from Anthropic or Twilio return a 500 with a clear JSON error message and do not crash the server.

---

### Step 9 – Safety, Disclaimers, and Future Compliance

**Goal:** Make sure from the start this is framed as **supportive tooling**, not medical software.

**Tasks:**

1. Add frontend banners & dialogs:
   
   * “This tool does not provide medical diagnosis or treatment.”
   * “Always consult a licensed healthcare professional.”

2. Add terms/privacy placeholders.

3. Architect for future HIPAA-style compliance:
   
   * Use environment variables and secrets for keys.
   * Use HTTPS in deployment.
   * Plan encryption for any PHI fields if/when real data is used.

**Prompt for Agent (Step 9):**

> In `/frontend`, add a persistent banner at the top of the dashboard that clearly states that the app does not provide diagnoses or treatment and is for connecting clinicians with patient data summaries.
> In `/backend`, add docstrings and comments reminding that this is not a medical device and that any real deployment must comply with healthcare privacy regulations.

---

## 5. System Architecture

### 5.1 High-Level Components

1. **Frontend Web App**
   
   * Patient selection
   * “Call Doctor Now” button
   * Displays call status and last summary.

2. **Backend API (FastAPI)**
   
   * Vitals repository (Postgres).
   * Risk engine.
   * Summary service (Claude).
   * Call service (Twilio).
   * Logging & auth.

3. **External Services**
   
   * Anthropic Claude API (text summarization).
   * Twilio Voice API (telephony).
   * (Future) Speech-to-text + real-time streaming.

4. **Database**
   
   * `vitals` table (Kaggle data).
   * `call_logs` table.

### 5.2 Sequence Flow – “Call Doctor Now”

1. **User clicks “Call Doctor Now”** on frontend with selected `patient_id`.

2. **Frontend → Backend**: `POST /call-doctor { patient_id }`.

3. **Backend:**
   
   1. Fetch last 2 hours of vitals via `VitalsRepository.get_recent_vitals`.
   2. Run `assess_risk` to get `risk_level` + signals.
   3. Call `generate_vitals_summary` → Claude → `summary_text`.
   4. Call `call_service.start_call(summary_text)` → Twilio.
   5. Insert `CallLog` row.
   6. Return `call_id` + message to frontend.

4. **Twilio:**
   
   * Initiates outbound call to `PROVIDER_PHONE_NUMBER`.
   
   * On answer, Twilio hits `/twilio/voice` webhook.
   
   * Backend returns TwiML that:
     
     * Plays disclaimer.
     * Reads `summary_text`.

5. **Frontend**:
   
   * Shows success message with `call_id`.
   * (Optional) polls `/calls/{call_id}/status`.

---

If you’d like, next step I can turn any one of these steps (e.g., Step 3 summary service, or Step 5 Twilio integration) into **concrete code skeletons** so you can drop them straight into your repo.
