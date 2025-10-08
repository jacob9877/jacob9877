import os, requests

import mysql.connector
from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from typing import Literal

from app.utils.assistants.clinician_pediatric_appendicitis_assistant import (
    GetPatientInfoInput,
    get_patient_info,
    GetPatientExplanationInput,
    explain_diagnosis,
    ClinicianPediatricAppendicitisAssistant,
)
from app.models.pediatric_appendicitis_models import FEATURE_NAMES
from app.models.conversation_models import Conversation
from app.utils.db import get_pediatric_appendicitis_patient_by_id

load_dotenv(find_dotenv(), override=True)

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

CHECKPOINT_NAMESPACE = "harry"


model = init_chat_model("google_genai:gemini-2.5-flash-lite", temperature=0)

def get_chat_response(conversation: Conversation, user_message: str) -> str:
    assistant = ClinicianPediatricAppendicitisAssistant(conversation)
    return assistant.invoke(user_message)

def get_gemini_title(message: str) -> str:
    return ClinicianPediatricAppendicitisAssistant.get_title(message)



