from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .routers import breast_cancer_patients, users

load_dotenv()
app = FastAPI()

# routers
app.include_router(users.router)
app.include_router(breast_cancer_patients.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Needs to be replaced with our domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = Mangum(app)
