import os

import mysql.connector
from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.models.mortality_patient_models import FEATURE_NAMES
from app.models.conversation_models import Conversation
from app.utils.db import get_mortality_patient_by_id

load_dotenv(find_dotenv(), override=True)

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

CHECKPOINT_NAMESPACE = "barry"

SYSTEM_PROMPT = """
You are a specialized medical AI agent for doctors focused on Pediatric Appendicitis named Harry. You have access to comprehensive information about Pediatric Appendicitis and tools to gain information about patients to provide to doctor users.

IMPORTANT INSTRUCTIONS:
1. Always prioritize information from the provided knowledge base and that can be obtained from the tools provided to you.
2. Feel free to use the tools to retrieve patient-specific information when needed to answer questions about pediatric patients with suspected appendicitis. If the conversation is about a specific patient, assume that the patient ID provided in the conversation context is the one to use for any patient-related queries. Otherwise, you may infer the patient ID from the user's questions.
3. If the question is answered in the knowledge base, reference that information
4. If the question is not fully covered in the knowledge base, use your general medical knowledge but clearly indicate this
5. Always recommend consulting with healthcare providers for personalized medical advice
6. Be empathetic and supportive when discussing patient concerns
7. Focus specifically on pediatric appendicitis topics
8. Keep responses brief. For example, one paragraph or up to 5 bullet points.

The system you are part of stores the following features about doctor's breast cancer patients' tumors:
- mean_radius: The mean radius of the tumor in millimeters
- mean_texture: The mean texture of the tumor in millimeters
- mean_perimeter: The mean perimeter of the tumor in millimeters
- mean_area: The mean area of the tumor in square millimeters
- mean_smoothness: The mean smoothness of the tumor, a dimensionless value
- Diagnosis (0 for benign, 1 for malignant): The predicted diagnosis of the tumor based on the features above
When requesting an explanation for a diagnosis, you will receive SHAP analysis that provides the contribution of each feature to the predicted diagnosis.

Please provide helpful, accurate information about breast cancer while emphasizing the importance of professional medical consultation.
"""


class GetPatientInfoInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the breast cancer patient to retrieve information for",
        example=123,
    )


@tool(
    description="Retrieve detailed information about a breast cancer patient given their patient ID. Call this tool when asked about any patient info not having to do with reasoning for the diagnosis.",
    args_schema=GetPatientInfoInput,
)
def get_patient_info(patient_id: int, *, config: RunnableConfig) -> dict:

    if patient_id != config["configurable"].get("patient_id"):
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

            patient = get_mortality_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    if patient.user_id != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    return patient.model_dump()


class GetPatientExplanationInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the breast cancer patient to retrieve explanation for",
        example=123,
    )


@tool(
    description="Explain a breast cancer patient's diagnosis using SHAP analysis based on their patient ID. Call this tool when asked for any reasoning behind the diagnosis.",
    args_schema=GetPatientExplanationInput,
)
def explain_diagnosis(patient_id: int, *, config: RunnableConfig) -> dict:

    # If the conversation is about a patient, make ture this tool call is about the same patient
    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):

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
            columns = (
                ["diagnosis", "user_id"]  # Columns from breast_cancer_patients table
                + FEATURE_NAMES  # Feature values from breast_cancer_patients table
                + [
                    f"contribution_{feature_name}" for feature_name in FEATURE_NAMES
                ]  # Contribution values from breast_cancer_explanations table
                + [
                    "patient_id",
                    "raw_probability",
                    "threshold",
                    "expected_value",
                ]  # Columns from breast_cancer_explanations table
            )

            operation = f"""
                SELECT {", ".join(columns)} 
                FROM breast_cancer_patients
                INNER JOIN breast_cancer_explanations
                    ON breast_cancer_patients.id = breast_cancer_explanations.patient_id
                WHERE breast_cancer_explanations.patient_id = %s
            """
            params = (patient_id,)
            cursor.execute(operation, params)
            row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation for patient with ID {patient_id} found",
        )

    if row["user_id"] != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

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


model = init_chat_model("google_genai:gemini-2.0-flash-lite", temperature=0)


def build_config(conversation: Conversation) -> dict:
    config = {
        "configurable": {
            "thread_id": str(conversation.id),  # LangGraph likes string thread_id
            "user_id": conversation.user_id,
            "patient_id": conversation.patient_id,
        },
        "checkpoint_ns": CHECKPOINT_NAMESPACE,
    }
    return config


def get_chat_response(conversation: Conversation, user_message: str) -> str:
    config = build_config(conversation)

    with PyMySQLSaver.from_conn_string(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ) as saver:

        prompt = SYSTEM_PROMPT
        if conversation.patient_id:
            prompt += f"You are chatting with a doctor about mortality patients with ID {conversation.patient_id}. If the user asks about any patient details you should call the appropriate tool with this patient id. If they ask any questions related to a patient assume it is about this patient with ID {conversation.patient_id}, and call the appropriate tools to gain relevant information."

        agent = create_react_agent(
            model=model,
            tools=[explain_diagnosis, get_patient_info],
            prompt=prompt,
            checkpointer=saver,
        )

        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ]
            },
            config,
        )
        ai_message = response["messages"][-1].content
        return ai_message


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
