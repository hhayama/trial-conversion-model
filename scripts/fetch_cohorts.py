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
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX)
    # Skip the "folder" placeholder key; ISO dates in file names sort chronologically
    keys = sorted(
        obj["Key"]
        for page in pages
        for obj in page.get("Contents", [])
        if not obj["Key"].endswith("/")
    )
    for key in keys:
        target = DEST / Path(key).name
        if target.exists():
            print(f"skip    {target}")
            continue
        s3.download_file(BUCKET, key, str(target))
        print(f"fetched {target}")


if __name__ == "__main__":
    main()
