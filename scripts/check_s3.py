import os

import boto3
from dotenv import load_dotenv

load_dotenv(override=True)
boto3.client("s3").head_bucket(Bucket=os.environ["BUCKET_NAME"])
print("credentials work")