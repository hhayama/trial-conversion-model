from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

BUCKET = "fpds-trial-cohorts"
PREFIX = "cohorts/"
DEST = Path("data/01_raw/cohorts")


def main() -> None:
    s3 = boto3.client(
        "s3", region_name="eu-north-1", config=Config(signature_version=UNSIGNED)
    )
    DEST.mkdir(parents=True, exist_ok=True)
    keys = sorted(
        obj["Key"]
        for obj in s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)["Contents"]
    )
    # ISO dates in the file names sort chronologically
    for key in (keys[0], keys[-1]):
        target = DEST / Path(key).name
        if target.exists():
            print(f"skip    {target}")
            continue
        s3.download_file(BUCKET, key, str(target))
        print(f"fetched {target}")


if __name__ == "__main__":
    main()
