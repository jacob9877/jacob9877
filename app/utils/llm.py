import json
import os
import sys

import mysql.connector
from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
from langchain.chat_models import init_chat_model
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent

from app.models.breast_cancer_patient_models import FEATURE_NAMES, BreastCancerPatient
from app.models.chat_models import Message
from app.models.conversation_models import Conversation
from app.utils.db import get_breast_cancer_patient_by_id

load_dotenv(find_dotenv(), override=True)

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

CHECKPOINT_NAMESPACE = "barry"

BREAST_CANCER_DOCUMENTS = """
TYPES OF BREAST CANCER:
1. DUCTAL CARCINOMA IN SITU (DCIS) - Non-invasive cancer in milk ducts
2. INVASIVE DUCTAL CARCINOMA (IDC) - Most common type, starts in ducts and spreads
3. INVASIVE LOBULAR CARCINOMA (ILC) - Starts in milk-producing glands
4. TRIPLE-NEGATIVE BREAST CANCER - Lacks estrogen, progesterone receptors, and HER2
5. HER2-POSITIVE BREAST CANCER - Has excess HER2 protein

RISK FACTORS:
- Age (risk increases after 50)
- Family history and genetic mutations (BRCA1, BRCA2)
- Dense breast tissue
- Hormone replacement therapy
- Obesity, alcohol consumption, lack of physical activity

SCREENING AND DIAGNOSIS:
- Mammography: Primary screening tool
- Ultrasound: For dense breasts or younger women
- MRI: For high-risk patients
- Biopsy: Definitive diagnosis
- Tumor markers: ER, PR, HER2 status

TREATMENT OPTIONS:
- Surgery: Lumpectomy or mastectomy
- Radiation therapy
- Chemotherapy
- Hormone therapy (for hormone receptor-positive cancers)
- Targeted therapy (e.g., for HER2-positive)

PREDICTION MODEL INFORMATION:
- Uses features: mean_radius, mean_texture, mean_perimeter, mean_area, mean_smoothness
- Predicts diagnosis: 0 (benign) or 1 (malignant)
- Provides SHAP analysis to explain feature importance in predictions

GENERAL INFORMATION:
- Early detection significantly improves outcomes
- Importance of regular screening
- Lifestyle factors for prevention
- Support resources for patients
"""

SYSTEM_PROMPT = f"""
You are a specialized medical AI agent focused on breast cancer named Barry. You have access to comprehensive information about breast cancer and tools to gain information about patients.

IMPORTANT INSTRUCTIONS:
1. Always prioritize information from the provided knowledge base and that can be obtained from the tools provided to you.
2. If the question is answered in the knowledge base, reference that information
3. If the question is not fully covered in the knowledge base, use your general medical knowledge but clearly indicate this
4. Always recommend consulting with healthcare providers for personalized medical advice
5. Be empathetic and supportive when discussing patient concerns
6. Focus specifically on breast cancer topics
7. Keep responses brief. For example, one paragraph or up to 5 bullet points.
8. When provided with prediction model results (in JSON format), explain them in natural language, including the diagnosis (benign (0) / malignant (1)) and the most important features from SHAP analysis that contributed to the prediction

KNOWLEDGE BASE:
{BREAST_CANCER_DOCUMENTS}

Please provide helpful, accurate information about breast cancer while emphasizing the importance of professional medical consultation.
"""


@tool
def get_patient_info(patient_id: int, *, config: RunnableConfig) -> BreastCancerPatient:
    """
    Retrieve detailed information about a breast cancer patient.
    -Inputs:
        - patient_id: integer ID (MySQL PK) of the breast cancer patient
    -Returns:
        - An object containing all feature values for the patient
    """

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

            patient = get_breast_cancer_patient_by_id(cursor, patient_id)

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

    return patient


@tool
def explain_diagnosis(patient_id: int, *, config: RunnableConfig) -> dict:
    """
    Explain a patient's breast cancer diagnosis.
    Returns a SHAP-based breakdown of feature contributions.
    -Inputs:
        - patient_id: integer ID (MySQL PK) of the breast cancer patient. Example: 123
    -Returns:
        - An object containing the raw probability output, threshold used for classification,
            the diagnosis (threshold applied to probability), expected value, and contributions for each feature.
    """

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
            prompt += f"You are chatting with a doctor about breast cancer patient with ID {conversation.patient_id}. If the user asks about any patient details you should call the appropriate with this patient id. If they ask any questions related to a patient assume it is about the patient with ID {conversation.patient_id}, and call the appropriate tools to gain relevant information."

        agent = create_react_agent(
            model=model,
            tools=[explain_diagnosis],
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


def get_conversation_history(conversation: Conversation) -> list[Message]:
    config = build_config(conversation)

    with PyMySQLSaver.from_conn_string(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ) as saver:

        snapshot = saver.get(config)

        print(snapshot)

    messages = []
    for message in snapshot["channel_values"].get("messages", []):
        if isinstance(message, AIMessage) and message.content != "":
            messages.append(Message(role="assistant", content=message.content))
        elif isinstance(message, HumanMessage):
            messages.append(Message(role="user", content=message.content))

    return messages


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
    return response.content
    return response.content
