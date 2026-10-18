import json
import os
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv
from evidently import Report
from evidently.presets import DataDriftPreset

from trial_conversion_model.data import RAW_DATA
from trial_conversion_model.features import add_features, FEATURES

# The convention the report is built with: the dataset counts as drifted
# when at least half of the features have drifted individually.
DRIFT_SHARE = 0.5
REPORT_DIR = Path("monitoring")

def load_reference(path: Path = RAW_DATA) -> pd.DataFrame:
    """The training extract is the reference: what normal looked like."""
    return pd.read_csv(path)

def load_parquet(path: Path) -> pd.DataFrame:
    """Takes a parquet file and returns a Pandas DataFrame"""
    return pd.read_parquet(path)

def run_drift_check(current: pd.DataFrame, reference: pd.DataFrame) -> object:
    """Compare current trials against the reference, feature by feature.

    Labels for live trials are 11+ days away, so input drift is the
    earliest signal that the world has shifted under the model.
    """
    reference["trial_started_at"] = pd.to_datetime(reference["trial_started_at"])
    cur = add_features(current)
    ref = add_features(reference)
    report = Report([DataDriftPreset(drift_share=0.5)])
    snapshot = report.run(reference_data=ref[FEATURES], current_data=cur[FEATURES])
    return snapshot


def drifted_share(snapshot: object) -> float:
    """Pull the share of drifted feature columns out of the report."""
    for metric in json.loads(snapshot.json())["metrics"]:
        if metric["metric_name"].startswith("DriftedColumnsCount"):
            return float(metric["value"]["share"])
    raise ValueError("drift metric missing from report")


def publish_report(snapshot: object, name: str) -> dict:
    """Write the report locally (HTML for eyes, JSON for machines) and to S3."""
    load_dotenv(override=True)
    REPORT_DIR.mkdir(exist_ok=True)
    html_path = REPORT_DIR / f"drift_{name}.html"
    json_path = REPORT_DIR / f"drift_{name}.json"
    snapshot.save_html(str(html_path))
    share = drifted_share(snapshot)
    json_path.write_text(
        json.dumps({"name": name, "drifted_share": share, "drift": share >= DRIFT_SHARE})
    )

    bucket = os.environ["S3_BUCKET"]
    s3 = boto3.client("s3")
    for path in (html_path, json_path):
        s3.upload_file(str(path), bucket, f"monitoring/{path.name}")
    return {"drifted_share": share, "drift": share >= DRIFT_SHARE}

def run_monitoring_pipeline(current: Path) -> dict:
    ref = load_reference()
    cur = load_parquet(current)
    drift_result = run_drift_check(current=cur, reference=ref)
    report_results = publish_report(drift_result, current.stem)
    return report_results
