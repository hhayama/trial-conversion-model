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
- `S3_BUCKET`: the bucket that holds the published model, the scored cohorts, and the drift reports.
- `SLACK_WEBHOOK_URL`: optional. Incoming-webhook URL for drift alerts; if unset, the alert is only printed.

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

## Batch scoring

Besides the on-demand API, the newest day-3 cohort is scored in bulk once a day, so the growth team gets a ranked list of the trials least likely to convert:

```
uv run scripts/score.py
```

It downloads the newest cohort file from the public, read-only cohort bucket (no credentials needed for that step; see `cohorts.py`), scores every trial with `models/model.json`, and sorts the result with the least likely to convert first. The output goes to `data/04_predictions/scored_<date>.csv` and is uploaded to `s3://$S3_BUCKET/predictions/`, so `S3_BUCKET` and AWS credentials must be set. The probability column is `prediction_prob`. Catch-up runs after missed days just score the most recent cohort.

### Backfilling history

On a fresh bucket the dashboard has nothing to show. To seed it, run once:

```
uv run scripts/backfill.py
```

This writes 30 days of synthetic scored cohorts and clean drift verdicts to the bucket, replacing anything already there for those days. It is a one-time fill, not part of the system, and should never be scheduled.

## Dashboard

A Streamlit dashboard reads the scored cohorts (`predictions/`) and drift verdicts (`monitoring/`) from S3 and shows the last 30 days: daily prediction distribution (mean with p25–p75 and p10–p90 bands), drift share against the alert threshold, and the current conversion-probability distribution. It also reads `models/metrics.json` for the model's headline metric, so train (or download) a model first.

```
uv run streamlit run dashboard/app.py
```

It needs `S3_BUCKET` and AWS credentials in `.env`. Data is cached for 10 minutes. Streamlit is in the dev dependency group.

## Scheduled jobs

In production, two daily jobs run from cron on the EC2 host, each in a short-lived container started from the jobs image (`Dockerfile.jobs`):

- `scripts/score.py`: batch scoring, as above.
- `scripts/check_drift.py`: drift check on the newest cohort (see below).

The jobs image holds code and the model but never data; `-v` mounts `/home/ubuntu/data` so the cohort pulled by the scoring run survives until the drift run. The exact `docker run` command is documented at the bottom of `Dockerfile.jobs`. CI builds and pushes the jobs image alongside the API image and pulls it onto the host on every deploy to `main`, so a pushed change takes effect in the next morning's run.

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

With no argument it checks the newest cohort already in `data/01_raw/cohorts/`. It prints a one-line verdict, for example `OK: 12% of features drifted (<cohort file>.parquet)` or `DRIFT: 58% of features ...`. For each cohort it also writes `monitoring/drift_<cohort>.html` (the full report, for people) and `monitoring/drift_<cohort>.json` (the share and verdict, for machines), and uploads both to `s3://$S3_BUCKET/monitoring/`. Both the reference extract and S3 credentials are needed, so run `fetch_data.py` and set up `.env` first. Drift reports are not committed.

When the verdict is `DRIFT`, the same message is also posted to Slack through `SLACK_WEBHOOK_URL` (see Configuration). `OK` verdicts are not posted.

## Layout

- `src/trial_conversion_model/`: the package. `data.py` acquires the extract from the database and loads the pipeline's inputs; `features.py` derives the model features from the snapshot's base aggregates and writes the processed training table; `train.py` trains, evaluates, and saves the model; `predict.py` scores trials from their base aggregates; `publish_model.py` uploads the trained model to S3; `monitoring.py` runs the input drift check, publishes its report, and sends the Slack alert; `cohorts.py` pulls the newest day-3 cohort; `api/` is the FastAPI service (`main.py` builds the app, `routes.py` holds the endpoints, `schemas.py` defines the request and response shapes, `logging_config.py` sets up the prediction log).
- `scripts/`: thin entry points that call into the package (`fetch_data.py` materializes the extract, `train.py` builds the training table and trains, `publish_model.py` pushes the model to S3, `fetch_cohorts.py` and `check_drift.py` run the drift workflow, `score.py` batch-scores the newest cohort, `backfill.py` seeds a month of history for the dashboard, `check_s3.py` and `testing_s3_connection.py` verify S3 access). Production runs these; the logic stays importable and testable in `src/`.
- `dashboard/`: the Streamlit monitoring dashboard (`app.py`).
- `Dockerfile`, `Dockerfile.jobs`: the API image and the scheduled-jobs image.
- `notebooks/`: exploration only. Notebooks import from the package; no pipeline logic lives here.
- `data/01_raw/`: the immutable extract as pulled from the database (never committed, never modified).
- `data/02_interim/`: reserved for intermediate outputs in multi-step pipelines; this project goes straight from raw to processed, so it stays empty.
- `data/03_processed/`: the model-ready training table written by the pipeline (never committed).
- `data/04_predictions/`: scored cohorts written by `score.py` (never committed).
- `models/`: trained model artifacts and metrics (not committed).
- `tests/`: pytest suite for the features and the API.
- `logs/`, `monitoring/`: prediction logs and drift reports written at runtime (not committed).
