import sys
from pathlib import Path

from trial_conversion_model.monitoring import alert, run_monitoring_pipeline

COHORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "01_raw" / "cohorts"

if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.exit("usage: uv run scripts/check_drift.py [cohort file]")
    if len(sys.argv) == 2:
        cohort_path = Path(sys.argv[1])
    else:
        # cohort filenames embed the date, so the max name is the newest cohort
        cohorts = sorted(COHORTS_DIR.glob("cohort_*.parquet"))
        if not cohorts:
            sys.exit(f"no cohort files found in {COHORTS_DIR}")
        cohort_path = cohorts[-1]
    result = run_monitoring_pipeline(cohort_path)
    verdict = "DRIFT" if result["drift"] else "OK"
    message = f"{verdict}: {result['drifted_share']:.0%} of features drifted in {cohort_path.name}. Latest report is in S3 under monitoring/"
    if verdict == "DRIFT":
        alert(message)
    print(message)
