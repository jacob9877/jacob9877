import os

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.models.common_models import ResponseModel
from app.routers import (
    auth,
    breast_cancer_patients,
    chat,
    conversations,
    mortality_patients,
    pediatric_appendicitis_patients,
    users,
)

load_dotenv(find_dotenv(), override=True)

app = FastAPI(
    root_path="/beta",
    title="AI for Bariatric Surgery API",
    description="All responses except auto-thrown 422 codes will follow standard response model with keys 'data' and 'detail'. Never infer anything about the value of the 'detail' key, use the status code instead.",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)  # root_path must match the API Gateway stage name


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ResponseModel[None](detail=exc.detail).model_dump(),
    )


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ResponseModel[None](detail=str(exc)).model_dump(),
    )


# routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(breast_cancer_patients.router)
app.include_router(pediatric_appendicitis_patients.router)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(mortality_patients.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", os.environ["FRONTEND_URL"]],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the AI for Bariatric Surgery API!"}


handler = Mangum(app)
