from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.routers import breast_cancer_patients, users, conversations

load_dotenv()
app = FastAPI(root_path="/beta")

# routers
app.include_router(users.router)
app.include_router(breast_cancer_patients.router)
app.include_router(conversations.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Needs to be replaced with our domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the AI for Bariatric Surgery API!"}


handler = Mangum(app)
