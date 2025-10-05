import json
import os
import uuid

import backoff
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.models.pediatric_appendicitis_models import (
    ACCEPTED_IMAGE_TYPES,
    MIME_TYPE_MAPPINGS,
)

ATTEMPTS = 4


def get_predictions(body: dict, sagemaker_endpoint_name) -> dict:
    sagemaker_client = boto3.client(
        "sagemaker-runtime",
        config=Config(retries={"max_attempts": ATTEMPTS, "mode": "standard"}),
    )

    # Apply exponential backoff to endpoint invocation with max wait time of 16s
    @backoff.on_exception(
        backoff.expo,
        sagemaker_client.exceptions.ModelNotReadyException,
        max_tries=ATTEMPTS,
        max_value=16,
        jitter=backoff.full_jitter,
    )
    def _invoke_endpoint():
        return sagemaker_client.invoke_endpoint(
            EndpointName=sagemaker_endpoint_name,
            ContentType="application/json",
            Body=json.dumps(body),
        )

    try:
        response = _invoke_endpoint()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model is unavailable {str(e)}",
        ) from e

    result_raw = response["Body"].read().decode("utf-8")
    result = json.loads(result_raw)
    return result


def bulk_send_message_to_sqs(queue_url: str, messages: list[dict]) -> None:
    sqs = boto3.client("sqs")

    for i in range(0, len(messages), 10):
        batch = messages[i : i + 10]

        entries = [
            {"Id": str(uuid.uuid4()), "MessageBody": json.dumps(message)}
            for message in batch
        ]

        sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)


def create_presigned_url(
    bucket: str, key: str, expires_in_sec: int | None = 3600
) -> str:

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client("s3")
    response = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in_sec,
    )

    # The response contains the presigned URL
    return response


def create_presigned_post_for_image(
    bucket: str,
    key: str,
    file_type: ACCEPTED_IMAGE_TYPES,
    max_size_in_bytes: int,
    expires_in_sec: int = 60,
):
    content_type = MIME_TYPE_MAPPINGS.get(file_type)
    if not content_type:
        raise ValueError(f"Unsupported file type: {file_type}")

    s3 = boto3.client(
        "s3",
        region_name=os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1",
        config=Config(signature_version="s3v4"),
    )

    fields = {
        "key": key,
        "Content-Type": content_type,
    }
    conditions = [
        {"bucket": bucket},
        {"key": key},
        {"Content-Type": content_type},
        ["content-length-range", 0, max_size_in_bytes],
    ]

    response = s3.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expires_in_sec,
    )

    return response


def s3_file_exists(bucket: str, key: str):
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            # Handle other potential errors (e.g., permissions)
            print(f"An error occurred: {e}")
            raise
            raise
            raise
