from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def hello():
    return {"detail": "Welcome to the AI for Bariatric Surgery API!"}

handler = Mangum(app)
