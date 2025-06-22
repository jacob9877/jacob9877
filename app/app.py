import json
from logging import getLogger

import boto3
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

logger = getLogger(__name__)
load_dotenv(find_dotenv(), override=True)

app = FastAPI()


@app.get("/")
def hello():
    return {"detail": "Welcome to the AI for Bariatric Surgery API!"}


class BreastCancerPrediction(BaseModel):
    mean_radius: float
    mean_texture: float
    mean_perimeter: float
    mean_area: float
    mean_smoothness: float


@app.post(
    "/breast-cancer",
    response_description="Predict on an instance of breast cancer data",
)
def test2(data: BreastCancerPrediction):
    client = boto3.client("sagemaker-runtime")

    instance = list(data.model_dump().values())

    response = client.invoke_endpoint(
        EndpointName="breast-cancer-endpoint",
        Body=json.dumps({"instances": [instance]}),
        ContentType="application/json",
    )

    return json.loads(response["Body"].read().decode("utf-8"))


handler = Mangum(app)
