from logging import getLogger

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from mangum import Mangum

logger = getLogger(__name__)
load_dotenv(find_dotenv())

app = FastAPI()


@app.get("/")
def hello():
    return {"detail": "Welcome to the AI for Bariatric Surgery API!"}


@app.post("/test1")
def test1():
    return {"detail": "Test 1 successful!"}


@app.post("/test2")
def test2():
    return {"detail": "Test 2 successful!"}


handler = Mangum(app)
