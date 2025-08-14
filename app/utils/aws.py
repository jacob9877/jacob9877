import json
from typing import Literal

import boto3


def get_predictions(
    instances: list[list[float]], sagemaker_endpoint_name
) -> list[Literal[0, 1]]:
    sagemaker_client = boto3.client("sagemaker-runtime")
    response = sagemaker_client.invoke_endpoint(
        EndpointName=sagemaker_endpoint_name,
        ContentType="application/json",
        Body=json.dumps({"instances": instances}),
    )
    result_raw = response["Body"].read().decode("utf-8")
    result = json.loads(result_raw)
    predictions = [
        prediction[0] if isinstance(prediction, list) else prediction
        for prediction in result["predictions"]
    ]
    return predictions
