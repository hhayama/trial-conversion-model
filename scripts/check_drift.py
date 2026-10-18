import sys
from pathlib import Path

from trial_conversion_model.monitoring import run_monitoring_pipeline

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: uv run scripts/check_drift.py <cohort file>")
    cohort_path = Path(sys.argv[1])
    result = run_monitoring_pipeline(cohort_path)
    verdict = "DRIFT" if result["drift"] else "OK"
    print(f"{verdict}: {result['drifted_share']:.0%} of features drifted ({cohort_path.name})")