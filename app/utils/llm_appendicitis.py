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

from app.models.pediatric_appendicitis_models import FEATURE_NAMES, DiagnoseImageInput
from app.models.conversation_models import Conversation
from app.utils.db import get_pediatric_appendicitis_patient_by_id

load_dotenv(find_dotenv(), override=True)

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

CHECKPOINT_NAMESPACE = "harry"

SYSTEM_PROMPT = """
You are a specialized medical AI agent for doctors focused on Pediatric Appendicitis named Harry. 
You have access to comprehensive information about Pediatric Appendicitis and tools to gain information about patients.

TOOL USAGE RULES:
- If the user refers to "patient X" or just a number (e.g. "3"), interpret this as patient_id=X and call the get_patient_info tool.
- If a patient_id is provided in the conversation context, assume it applies.
- If no patient_id is set in the conversation context, infer the patient_id from the user’s message.
- Always use the tools when retrieving patient details.
- If no patient is found, respond empathetically.
- If the user asks about reasoning for a diagnosis, use the explain_diagnosis tool.
- If the user uploads or references an appendicitis image, use the diagnose_appendicitis_image tool.

IMPORTANT INSTRUCTIONS:
1. Prioritize information from the tools and knowledge base first.
2. Use your general medical knowledge only when the tools or knowledge base do not fully answer the question, and clearly indicate this.
3. Always recommend consulting with healthcare providers for personalized medical advice.
4. Be empathetic and supportive when discussing patient concerns.
5. Keep responses concise: one paragraph or up to 5 bullet points.

DATA AVAILABLE:
The system stores the following patient features:
- Age
- BMI
- Sex
- Height
- Weight
When requesting an explanation for a diagnosis, you will receive SHAP analysis that provides the contribution of each feature to the predicted diagnosis.

IMAGE ANALYSIS INSTRUCTIONS:
- If an image is uploaded, summarize results in this format:
  • Diagnosis (appendicitis / no appendicitis)
  • Severity (complicated / uncomplicated)
  • Management (surgical / conservative)
  • Predicted length of stay (in days)

Always provide accurate information about pediatric appendicitis while emphasizing the importance of professional medical consultation.
"""


class GetPatientInfoInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the pediatric appendicitis patient to retrieve information for",
        example=123,
    )


@tool(
    description="Retrieve detailed information about a pediatric appendicitis patient given their patient ID. Call this tool when asked about any patient info not having to do with reasoning for the diagnosis.",
    args_schema=GetPatientInfoInput,
)
def get_patient_info(patient_id: int, *, config: RunnableConfig) -> dict:

    if config["configurable"].get("patient_id") and patient_id != config["configurable"]["patient_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
    )


    with mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    ) as conn:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    # if patient.user_id != config["configurable"].get("user_id"):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User is not authorized to access this patient's data",
    #     )

    return patient.model_dump()


class GetPatientExplanationInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the breast cancer patient to retrieve explanation for",
        example=123,
    )


@tool(
    description="Explain a pediatric appendicitis patient's diagnosis using SHAP analysis based on their patient ID. Call this tool when asked for any reasoning behind the diagnosis.",
    args_schema=GetPatientExplanationInput,
)
def explain_diagnosis(patient_id: int, *, config: RunnableConfig) -> dict:

    # If the conversation is about a patient, make ture this tool call is about the same patient
    # if config["configurable"].get("patient_id") and patient_id != config["configurable"].get("patient_id"):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Tool input patient_id does not match the patient_id of the conversation scope.",
    #     )

    with mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    ) as conn:
        with conn.cursor(dictionary=True) as cursor:
            columns = (
                [
                    "diagnosis",
                    "user_id",
                ]  # Columns from pediatric_appendicitis_patients table
                + FEATURE_NAMES  # Feature values from pediatric_appendicitis_patients table
                + [
                    f"contribution_{feature_name}" for feature_name in FEATURE_NAMES
                ]  # Contribution values from pediatric_appendicitis_explanations table
                + [
                    "patient_id",
                    "raw_probability",
                    "threshold",
                    "expected_value",
                ]  # Columns from pediatric_appendicitis_explanations table
            )

            operation = f"""
                SELECT {", ".join(columns)}
                FROM pediatric_appendicitis_patients
                INNER JOIN pediatric_appendicitis_explanations
                    ON pediatric_appendicitis_patients.id = pediatric_appendicitis_explanations.patient_id
                WHERE pediatric_appendicitis_explanations.patient_id = %s
            """
            params = (patient_id,)
            cursor.execute(operation, params)
            row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation for patient with ID {patient_id} found",
        )

    # if row["user_id"] != config["configurable"].get("user_id"):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User is not authorized to access this patient's data",
    #     )

    result = {
        "feature_values": {},
        "explanation": {
            "raw_probability": row["raw_probability"],
            "threshold": row["threshold"],
            "diagnosis": (1 if row["raw_probability"] >= row["threshold"] else 0),
            "expected_value": row["expected_value"],
            "contributions": [],
        },
    }
    for feature_name in FEATURE_NAMES:
        result["feature_values"][feature_name] = row[feature_name]
        contribution_value = row[f"contribution_{feature_name}"]
        result["explanation"]["contributions"].append(
            {
                "feature": feature_name,
                "value": contribution_value,
                "magnitude": abs(contribution_value),
                "direction": "up" if contribution_value > 0 else "down",
            }
        )

    return result


@tool(
    description="Upload an appendicitis image and return diagnosis, severity, management, and predicted length of stay.",
    args_schema=DiagnoseImageInput,
)
def diagnose_appendicitis_image(file_path: str, *, config: RunnableConfig) -> dict:
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
    AUTH_HEADER = {"Authorization": f"Bearer {os.environ.get('USER_TOKEN', '')}"}

    # 1. Request presigned upload
    presigned = requests.post(
        f"{API_BASE}/pediatric-appendicitis-patients/images",
        json={"file_types": ["jpg"]},  # could be detected dynamically
        headers=AUTH_HEADER,
    ).json()[0]
    upload_id = presigned["upload_id"]

    # 2. Upload to S3
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f)}
        requests.post(presigned["url"], data=presigned["fields"], files=files)

    # 3. Create patient with minimal valid features + image
    payload = {
        "features": {"Age": 10.0, "Sex": "female", "US_Performed": "yes"},
        "image_upload_ids": [upload_id],
    }
    patient = requests.post(
        f"{API_BASE}/pediatric-appendicitis-patients",
        json=payload,
        headers=AUTH_HEADER,
    ).json()["data"]

    return {
        "diagnosis": patient["diagnosis"],
        "severity": patient["severity"],
        "management": patient["management"],
        "length_of_stay_days": patient["length_of_stay_pred"],
        "image_url": patient["images"][0]["url"],
    }


model = init_chat_model("google_genai:gemini-2.5-flash-lite", temperature=0)


def build_config(conversation: Conversation) -> dict:
    config = {
        "configurable": {
            "thread_id": f"pediatric_appendicitis_patients-{conversation.id}",
            "user_id": conversation.user_id,
            "patient_id": conversation.patient_id,
        },
        "checkpoint_ns": CHECKPOINT_NAMESPACE,
    }
    return config


# def get_chat_response(conversation: Conversation, user_message: str) -> str:
#     config = build_config(conversation)

#     with PyMySQLSaver.from_conn_string(
#         f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
#     ) as saver:

#         prompt = SYSTEM_PROMPT
#         if conversation.patient_id:
#             prompt += f"You are chatting with a doctor about pediatric appendicitis patients with ID {conversation.patient_id}. If the user asks about any patient details you should call the appropriate tool with this patient id. If they ask any questions related to a patient assume it is about this patient with ID {conversation.patient_id}, and call the appropriate tools to gain relevant information."

#         agent = create_react_agent(
#             model=model,
#             tools=[explain_diagnosis, get_patient_info],
#             prompt=prompt,
#             checkpointer=saver,
#         )


#         response = agent.invoke(
#             {
#                 "messages": [
#                     {
#                         "role": "user",
#                         "content": user_message,
#                     }
#                 ]
#             },
#             config,
#         )
#         ai_message = response["messages"][-1].content
#         return ai_message
def get_chat_response(conversation: Conversation, user_message: str) -> str:
    with PyMySQLSaver.from_conn_string(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ) as saver:
        response = graph.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            {
                **build_config(conversation),
                "checkpointer": saver,
                "if_not_exists": "create",
            },
        )

    return response["messages"][-1].content


TITLE_SYSTEM_PROMPT = """
You are an expert in creating concise but expressive titles.
You will create titles for a chatbot where users can have multiple conversations.
You will take in the user's first message and create a concise title (40 characters or less) for the conversation.
The title should concisely describe what the conversation is about and what the user is asking.
The casing should be that of a sentence: The first word should be capitalized but everything else (except names) should be lowercase
"""


def get_gemini_title(message: str) -> str:

    messages = [("system", TITLE_SYSTEM_PROMPT), ("human", message)]
    response = model.invoke(messages)
    return response.content


graph = create_react_agent(
    model=model,
    tools=[explain_diagnosis, get_patient_info, diagnose_appendicitis_image],
    prompt=SYSTEM_PROMPT,
)
