import os

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
S3_BUCKET = os.environ["S3_BUCKET"]
S3_MODEL_PATH = "models"  # model path and filename
LOCAL_MODEL_PATH = 'models'
MODEL_FILE_NAME = 'model.json'

def publish_model():
    # Initialize S3
    s3_client = boto3.client("s3")

    # Create path structures
    s3_key = f"{S3_MODEL_PATH}/{MODEL_FILE_NAME}"
    local_file_path = os.path.join(LOCAL_MODEL_PATH, MODEL_FILE_NAME)

    # Try upload and 
    try:
        print(f"Uploading to s3://{S3_BUCKET}/{s3_key} ...")
        s3_client.upload_file(local_file_path, S3_BUCKET, s3_key)
        print("Upload successful!")
        
        # 4. Verify object existence in S3
        response = s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        print(f"Verified object in S3 (Size: {response['ContentLength']} bytes)")
        
    except NoCredentialsError:
        print("Error: AWS credentials not found. Make sure your environment variables or AWS config are set.")
    except ClientError as e:
        print(f"S3 Error: {e.response['Error']['Message']} (Code: {e.response['Error']['Code']})")
    except Exception as e: #noqa: BLE001
        print(f"Unexpected error: {e}")


