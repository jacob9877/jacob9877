from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from mangum import Mangum

load_dotenv(find_dotenv())

app = FastAPI()


@app.get("/")
def hello():
    return {"detail": "Welcome to the AI for Bariatric Surgery API!"}


handler = Mangum(app)
