# trial-conversion-model

Predicts, from a trial's first 3 days of behavior, whether the trial will convert to a paid plan at the end of day 14, so the growth team can reach trials that look unlikely to convert while they are still live. The business case and rollout plan are in the model plan document.

## Setup

Install the dependencies and the package:

```
uv sync
```

The training data is not committed to the repository. Copy `.env.example` to `.env` and replace the password placeholder with the one from the course's Tools & Setup lesson, then materialize the extract:

```
uv run scripts/fetch_data.py
```

This writes `data/01_raw/trial_snapshot.csv`. Training always runs from that file, never from the live table, so the training data cannot shift between runs.

### Configuration

`.env` also holds the settings for experiment tracking and S3 (see `.env.example`):

- `MLFLOW_TRACKING_URI`: where the MLflow tracking server lives (defaults in `.env.example` to `http://127.0.0.1:5001`).
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`: AWS credentials.
- `S3_BUCKET`: the bucket that holds the published model and the drift reports.

Check that your credentials and bucket work before relying on them:

```
uv run scripts/check_s3.py
```

This prints `credentials work` if the bucket is reachable. `scripts/testing_s3_connection.py` goes further and writes a small test object under `mlflow-connection-test/`.

## Train

```
uv run scripts/train.py
```

This builds the processed training table from the raw extract, trains the model, and writes `models/model.json` and `models/metrics.json`.

### Experiment tracking with MLflow

Each training run is logged to MLflow under the `trail-conversion-model` experiment: the hyperparameters and the test AUC. Start a tracking server on the port in `MLFLOW_TRACKING_URI` before training, then browse the runs in the UI at http://127.0.0.1:5001:

```
uv run mlflow server --port 5001
```

Local MLflow state (`mlruns/`, `mlflow.db`, `mlartifacts/`) is not committed.

### Publishing the model to S3

Once you are happy with a trained model, push `models/model.json` to `s3://$S3_BUCKET/models/model.json`:

```
uv run scripts/publish_model.py
```

It uploads the file and then confirms the object exists in S3. Errors (missing credentials, a denied upload) are printed rather than raised, so read the output instead of relying on the exit code.

CI downloads this published model, so the tests and the Docker image are built against whatever was last published. Publish before you push a model change.

## Serve

The model is served over HTTP so the teams that need scores can get them on demand. Run the service locally:

```
uv run uvicorn trial_conversion_model.api.main:app --reload
```

Or build and run it as a container, which is how it ships:

```
docker build -t trial-conversion-model .
docker run -p 8000:8000 trial-conversion-model
```

`POST /predict` takes one trial's first-3-day base aggregates and returns its conversion probability plus a low/medium/high band; `GET /health` reports service status and the package version. Interactive docs live at `/docs` while the service runs.

The image copies `models/model.json` in at build time, so the model must exist locally before `docker build` (train it, or download the published one from S3).

Every prediction is also logged as one JSON line to `logs/predictions.jsonl` (timestamp, the request, the probability, and the band). The `logs/` directory is not committed.

### Checking it works

With the service running, three requests and what each should come back with.

A steady trial, spread across the first three days:

```
curl -s -X POST localhost:8000/predict -H "Content-Type: application/json" -d '{
  "sessions_day1": 3, "sessions_day2": 2, "sessions_day3": 2,
  "listen_sessions_3d": 5, "total_minutes_3d": 180,
  "country": "US", "device_type": "iOS"
}'
```

```
{"conversion_probability":0.8593,"conversion_band":"high"}
```

The same trial's activity crammed into day one:

```
curl -s -X POST localhost:8000/predict -H "Content-Type: application/json" -d '{
  "sessions_day1": 9, "sessions_day2": 0, "sessions_day3": 0,
  "listen_sessions_3d": 4, "total_minutes_3d": 150,
  "country": "US", "device_type": "iOS"
}'
```

```
{"conversion_probability":0.3385,"conversion_band":"medium"}
```

A request with `sessions_day1` missing, which the contract turns down before any
of your code runs:

```
curl -i -s -X POST localhost:8000/predict -H "Content-Type: application/json" -d '{
  "sessions_day2": 0, "sessions_day3": 0,
  "listen_sessions_3d": 4, "total_minutes_3d": 150,
  "country": "US", "device_type": "iOS"
}'
```

```
HTTP/1.1 422 Unprocessable Entity
```

## Tests and CI

```
uv run ruff check .
uv run pytest
```

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main` and on pull requests. It lints, pulls the published model from S3, runs the tests, and builds the image. On pushes to `main` it then pushes the image to GitHub Container Registry and redeploys it to the EC2 host over SSH. It needs the repository secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `EC2_HOST`, and `EC2_SSH_KEY`.

## Monitoring input drift

Labels for live trials arrive 11+ days after scoring, so the earliest warning that the model is being fed different data than it was trained on is drift in the inputs. The drift check compares a cohort of recent trials against the training extract (`data/01_raw/trial_snapshot.csv`) on the model features, using Evidently. The dataset counts as drifted when at least half of the features have drifted.

Download the cohort files (parquet, one per cohort) into `data/01_raw/cohorts/`; files already downloaded are skipped:

```
uv run scripts/fetch_cohorts.py
```

Then check a cohort:

```
uv run scripts/check_drift.py data/01_raw/cohorts/<cohort file>.parquet
```

It prints a one-line verdict, for example `OK: 12% of features drifted (<cohort file>.parquet)` or `DRIFT: 58% of features ...`. For each cohort it also writes `monitoring/drift_<cohort>.html` (the full report, for people) and `monitoring/drift_<cohort>.json` (the share and verdict, for machines), and uploads both to `s3://$S3_BUCKET/monitoring/`. Both the reference extract and S3 credentials are needed, so run `fetch_data.py` and set up `.env` first. Drift reports are not committed.

## Layout

- `src/trial_conversion_model/`: the package. `data.py` acquires the extract from the database and loads the pipeline's inputs; `features.py` derives the model features from the snapshot's base aggregates and writes the processed training table; `train.py` trains, evaluates, and saves the model; `predict.py` scores trials from their base aggregates; `publish_model.py` uploads the trained model to S3; `monitoring.py` runs the input drift check and publishes its report; `api/` is the FastAPI service (`main.py` builds the app, `routes.py` holds the endpoints, `schemas.py` defines the request and response shapes, `logging_config.py` sets up the prediction log).
- `scripts/`: thin entry points that call into the package (`fetch_data.py` materializes the extract, `train.py` builds the training table and trains, `publish_model.py` pushes the model to S3, `fetch_cohorts.py` and `check_drift.py` run the drift workflow, `check_s3.py` and `testing_s3_connection.py` verify S3 access). Production runs these; the logic stays importable and testable in `src/`.
- `notebooks/`: exploration only. Notebooks import from the package; no pipeline logic lives here.
- `data/01_raw/`: the immutable extract as pulled from the database (never committed, never modified).
- `data/02_interim/`: reserved for intermediate outputs in multi-step pipelines; this project goes straight from raw to processed, so it stays empty.
- `data/03_processed/`: the model-ready training table written by the pipeline (never committed).
- `models/`: trained model artifacts and metrics (not committed).
- `tests/`: pytest suite for the features and the API.
- `logs/`, `monitoring/`: prediction logs and drift reports written at runtime (not committed).
