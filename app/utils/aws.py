import json
import time
import uuid
from typing import Literal

import boto3
from botocore.config import Config
from fastapi import HTTPException, status

ATTEMPTS = 4


def get_predictions(
    instances: list[list[float]], sagemaker_endpoint_name
) -> list[Literal[0, 1]]:
    sagemaker_client = boto3.client(
        "sagemaker-runtime",
        config=Config(retries={"max_attempts": ATTEMPTS, "mode": "standard"}),
    )

    delay_sec = 1
    for attempt in range(ATTEMPTS):
        try:
            response = sagemaker_client.invoke_endpoint(
                EndpointName=sagemaker_endpoint_name,
                ContentType="application/json",
                Body=json.dumps({"instances": instances}),
            )
            result_raw = response["Body"].read().decode("utf-8")
        except sagemaker_client.exceptions.ModelNotReadyException:
            # If reached max retry attempts
            if attempt == ATTEMPTS - 1:
                # Give up
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Model is unavailable even after retries",
                )
            time.sleep(delay_sec)
            delay = min(
                delay * 2, 16
            )  # Exponential backoff with max of 16 seconds delay

    result = json.loads(result_raw)
    predictions = [
        prediction[0] if isinstance(prediction, list) else prediction
        for prediction in result["predictions"]
    ]
    return predictions


def bulk_send_message_to_sqs(queue_url: str, messages: list[dict]) -> None:
    sqs = boto3.client("sqs")

    for i in range(0, len(messages), 10):
        batch = messages[i : i + 10]

        entries = [
            {"Id": str(uuid.uuid4()), "MessageBody": json.dumps(message)}
            for message in batch
        ]

        sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
