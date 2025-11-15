# vitals ingestion and repository

## overview

this module handles the ingestion of patient vital signs data and provides a repository layer for querying vitals from the database.

## components

### 1. data model (`backend/models/vitals.py`)

the `Vital` model represents a single vital signs reading for a patient at a specific timestamp.

**fields:**
- `id`: primary key (auto-increment)
- `patient_id`: unique patient identifier (indexed)
- `timestamp`: when vitals were recorded in utc (indexed)
- `heart_rate`: beats per minute (float)
- `respiratory_rate`: breaths per minute (float)
- `body_temperature`: degrees celsius (float)
- `spo2`: oxygen saturation percentage 0-100 (float)
- `systolic_bp`: systolic blood pressure mmhg (int)
- `diastolic_bp`: diastolic blood pressure mmhg (int)
- `age`: patient age in years (int)
- `gender`: patient gender (string)
- `pulse_pressure`: derived metric = systolic - diastolic (float)
- `mean_arterial_pressure`: derived metric = map (float)

**methods:**
- `to_dict()`: converts vital record to dictionary for json serialization

### 2. database configuration (`backend/config.py`)

manages database connection and session creation using sqlalchemy.

**key functions:**
- `get_db_session()`: creates and returns a new database session

**configuration:**
- uses sqlite by default (`DATABASE_URL=sqlite:///vitals.db`)
- supports environment variable configuration via `.env` file
- auto-creates tables on first run

### 3. vitals repository (`backend/repositories/vitals_repository.py`)

data access layer for querying patient vitals.

**methods:**

#### `get_recent_vitals(patient_id: str, window_hours: int = 2) -> List[Vital]`
fetches vitals for the last n hours for a specific patient.

**args:**
- `patient_id`: unique patient identifier
- `window_hours`: time window in hours (default 2)

**returns:**
- list of vital records, ordered by timestamp ascending (oldest first)

**example:**
```python
from backend.config import get_db_session
from backend.repositories.vitals_repository import VitalsRepository

session = get_db_session()
repo = VitalsRepository(session)
recent = repo.get_recent_vitals("PATIENT_001", window_hours=2)
print(f"found {len(recent)} vitals in last 2 hours")
```

#### `get_latest_vitals(patient_id: str) -> Optional[Vital]`
fetches the most recent vital reading for a patient.

**returns:**
- single vital record (most recent) or none if no data exists

#### `get_all_vitals(patient_id: str) -> List[Vital]`
fetches all vital records for a patient.

**returns:**
- list of all vital records, ordered by timestamp ascending

#### `count_vitals(patient_id: str) -> int`
counts total number of vital records for a patient.

**returns:**
- number of vital records

### 4. synthetic data generator (`scripts/ingest_vitals.py`)

generates realistic time-series vitals data with a deteriorating trend for testing.

**functions:**

#### `load_baseline_patient(csv_path: str) -> Dict`
loads baseline patient data from csv (first patient).

**returns:**
- dict containing baseline vital values

#### `generate_synthetic_timeseries(baseline: Dict, num_records: int = 150, patient_id: str = "PATIENT_001") -> List[Vital]`
generates synthetic time-series vitals with deteriorating trend.

**algorithm:**
- uses random walk with gaussian noise
- applies gradual deterioration trends:
  - heart rate: +0.15 bpm/min (with noise σ=2.5)
  - spo2: -0.03%/min (with noise σ=0.5)
  - systolic bp: +0.08 mmhg/min (with noise σ=3.0)
  - temperature: +0.002°c/min (with noise σ=0.15)
- clamps values to physiologically realistic bounds
- maintains systolic > diastolic constraint

**parameters:**
- `baseline`: dict with initial vital values from csv
- `num_records`: number of time-series points (default 150 = 2.5 hours)
- `patient_id`: patient identifier (default "PATIENT_001")

**returns:**
- list of vital model instances ready for database insertion

#### `ingest_vitals(csv_path: str, num_records: int = 150) -> int`
main ingestion function: loads baseline, generates synthetic data, inserts to db.

**workflow:**
1. loads baseline patient from vitals.csv
2. generates synthetic time-series data
3. creates database tables if not exist
4. bulk inserts all vitals
5. commits transaction

**returns:**
- number of records inserted

**usage:**
```bash
.venv/bin/python scripts/ingest_vitals.py
```

## data characteristics

### synthetic data properties

the generated vitals exhibit a **deteriorating trend** over 2.5 hours (150 records at 1-minute intervals):

**initial state (first 30 records avg):**
- heart rate: ~65 bpm
- spo2: ~95.5%
- systolic bp: ~118 mmhg

**deteriorated state (last 30 records avg):**
- heart rate: ~88 bpm (+23 bpm)
- spo2: ~91.5% (-4%)
- systolic bp: ~135 mmhg (+17 mmhg)

### physiological bounds

all vitals are clamped to realistic ranges:
- heart rate: 45-180 bpm
- respiratory rate: 8-30 breaths/min
- temperature: 35.0-41.0°c
- spo2: 70-100%
- systolic bp: 80-200 mmhg
- diastolic bp: 50-130 mmhg

## testing

comprehensive test suite in `tests/test_vitals_repository.py`:

1. **test_get_recent_vitals_returns_last_2_hours**: verifies time window filtering
2. **test_get_latest_vitals_returns_most_recent**: confirms latest record retrieval
3. **test_get_all_vitals_returns_all_records**: validates full record retrieval
4. **test_count_vitals_returns_correct_count**: checks record counting
5. **test_vitals_show_deteriorating_trend**: validates deterioration pattern
6. **test_vital_to_dict_method**: confirms serialization works

**run tests:**
```bash
.venv/bin/pytest tests/test_vitals_repository.py -v
```

## database schema

**table: vitals**
```sql
CREATE TABLE vitals (
    id INTEGER NOT NULL PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    timestamp DATETIME NOT NULL,
    heart_rate FLOAT NOT NULL,
    respiratory_rate FLOAT NOT NULL,
    body_temperature FLOAT NOT NULL,
    spo2 FLOAT NOT NULL,
    systolic_bp INTEGER NOT NULL,
    diastolic_bp INTEGER NOT NULL,
    age INTEGER NOT NULL,
    gender VARCHAR NOT NULL,
    pulse_pressure FLOAT,
    mean_arterial_pressure FLOAT
);

CREATE INDEX ix_vitals_patient_id ON vitals (patient_id);
CREATE INDEX ix_vitals_timestamp ON vitals (timestamp);
```

## future improvements

1. replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` to fix deprecation warnings
2. update to `declarative_base()` from `sqlalchemy.orm` instead of deprecated import
3. add data validation constraints (e.g., ensure systolic > diastolic)
4. implement caching for frequently accessed queries
5. add support for multiple patients
6. implement real-time data streaming from medical devices

## related files

- `backend/models/vitals.py`: data model
- `backend/config.py`: database configuration
- `backend/repositories/vitals_repository.py`: repository layer
- `scripts/ingest_vitals.py`: data generation and ingestion
- `tests/test_vitals_repository.py`: test suite
- `vitals.csv`: source data for baseline patient
- `vitals.db`: sqlite database file (generated)
