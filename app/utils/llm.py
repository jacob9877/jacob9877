import json
import os
import sys

import boto3
import mysql.connector
from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent

from app.models.breast_cancer_patient_models import FEATURE_NAMES, Explanation
from app.models.chat_models import Message

load_dotenv(find_dotenv(), override=True)

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")

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
You are a specialized medical AI assistant focused on breast cancer named Barry. You have access to comprehensive information about breast cancer and a prediction model that analyzes tumor features to predict malignancy.

IMPORTANT INSTRUCTIONS:
1. Always prioritize information from the provided knowledge base
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

EXPLAINER_LAMBDA_NAME = "breast-cancer-classifier-explainer"


@tool
def explain_diagnosis(
    patient_id: int,
) -> Explanation:
    """
    Explain a patient's breast cancer diagnosis.
    Returns a SHAP-based breakdown of feature contributions.
    -Inputs:
        - patient_id: integer ID (MySQL PK) of the breast cancer patient
    -Returns:
        - An object containing the raw probability output, threshold used for classification,
            the diagnosis (threshold applied to probability), expected value, and contributions for each feature.
    """

    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )
    cursor = conn.cursor(dictionary=True)

    operation = f"""
        SELECT {", ".join(FEATURE_NAMES)} 
        FROM breast_cancer_patients
        WHERE id = %s
    """
    params = (patient_id,)
    # Retrieve the patient's features
    cursor.execute(operation, params)
    patient_features = cursor.fetchone()

    # Invoke the explainer Lambda with the features
    lambda_client = boto3.client("lambda", region_name=os.environ["AWS_DEFAULT_REGION"])
    response = lambda_client.invoke(
        FunctionName=EXPLAINER_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(patient_features),
    )

    raw = response.get("Payload").read().decode("utf-8")
    explanation_json = json.loads(raw)
    explanation = Explanation(**explanation_json)

    # Update the patient's diagnosis in case their old diagnosis was on an earlier version of the model so maybe it will change
    operation = """ 
        UPDATE breast_cancer_patients
        SET diagnosis = %s
        WHERE id = %s
    """
    params = (
        explanation.diagnosis,
        patient_id,
    )
    cursor.execute(operation, params)
    conn.commit()

    return explanation


model = init_chat_model("google_genai:gemini-2.0-flash-lite", temperature=0)


def get_chat_response(conversation_id: int, user_id: int, user_message: str) -> str:

    config = {
        "configurable": {"thread_id": conversation_id},
        "metadata": {"user_id": user_id},
    }

    with PyMySQLSaver.from_conn_string(
        f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ) as saver:

        agent = create_react_agent(
            model=model,
            tools=[],  # Excluded explain tool because it takes so long
            prompt=SYSTEM_PROMPT,
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


def get_conversation_history(conversation_id: int) -> list[Message]:
    config = {
        "configurable": {"thread_id": conversation_id},
    }

    with PyMySQLSaver.from_conn_string(
        f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ) as saver:
        snapshot = saver.get(config)

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
