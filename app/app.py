from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from routers import register, login

load_dotenv()
app = FastAPI()

# routers
app.include_router(register.router)
app.include_router(login.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Needs to be replaced with our domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = Mangum(app)
