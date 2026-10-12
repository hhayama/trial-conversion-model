import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
BUCKET_NAME = os.environ["BUCKET_NAME"]
S3_BASE_PREFIX = "mlflow-connection-test"  # Base folder in S3

def test_s3_write():
    # 1. Generate current timestamp for path and file naming
    now = datetime.now(UTC)
    timestamp_folder = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"test_{timestamp_folder}.txt"
    
    # S3 destination path: mlflow-connection-test/2026-10-04_11-17-00/test_2026-10-04_11-17-00.txt
    s3_key = f"{S3_BASE_PREFIX}/{timestamp_folder}/{filename}"
    
    # 2. Create local temporary directory & file
    local_dir = f"tmp_{timestamp_folder}"
    os.makedirs(local_dir, exist_ok=True)
    local_file_path = os.path.join(local_dir, filename)
    
    with open(local_file_path, "w", encoding="utf-8") as f:
        f.write("hello world\n")
    
    print(f"Created local file: {local_file_path}")

    # 3. Initialize S3 client & test upload
    s3_client = boto3.client("s3")
    
    try:
        print(f"Uploading to s3://{BUCKET_NAME}/{s3_key} ...")
        s3_client.upload_file(local_file_path, BUCKET_NAME, s3_key)
        print("Upload successful!")
        
        # 4. Verify object existence in S3
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        print(f"Verified object in S3 (Size: {response['ContentLength']} bytes)")
        
    except NoCredentialsError:
        print("Error: AWS credentials not found. Make sure your environment variables or AWS config are set.")
    except ClientError as e:
        print(f"S3 Error: {e.response['Error']['Message']} (Code: {e.response['Error']['Code']})")
    except Exception as e: #noqa: BLE001
        print(f"Unexpected error: {e}")
        
    finally:
        # Cleanup local file and temp directory
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        if os.path.exists(local_dir):
            os.rmdir(local_dir)
        print("Cleaned up local temporary files.")

if __name__ == "__main__":
    test_s3_write()