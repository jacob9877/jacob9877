import json
from typing import Literal

import requests
from fastapi import HTTPException, status
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.models.conversation_models import AssistantSlug, Conversation
from app.utils.assistants.base_assistant import Assistant
from app.utils.db import (
    db_connection_cm,
    get_breast_cancer_patient_by_id,
    get_db_connection_string,
)


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

    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    with db_connection_cm() as conn:
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

    with db_connection_cm() as conn:
        with conn.cursor(dictionary=True) as cursor:

            operation = """
                SELECT bce.explanation,
                    bcp.user_id
                FROM breast_cancer_explanations AS bce
                JOIN breast_cancer_patients AS bcp
                ON bce.patient_id = bcp.id
                WHERE bce.patient_id = %s
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

    return json.loads(row["explanation"])


OverallStatusOptions = Literal[
    "ACTIVE_NOT_RECRUITING",
    "COMPLETED",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
    "RECRUITING",
    "SUSPENDED",
    "TERMINATED",
    "WITHDRAWN",
    "AVAILABLE",
    "NO_LONGER_AVAILABLE",
    "TEMPORARILY_NOT_AVAILABLE",
    "APPROVED_FOR_MARKETING",
    "WITHHELD",
    "UNKNOWN",
]


class GetClinicalTrialsInput(BaseModel):
    condition: str = Field(
        ...,
        description="Name of the condition the clinical trial is for",
        example="lung cancer",
    )
    overall_status: list[OverallStatusOptions] | None = Field(
        default=None,
        description="Status of clinical trials to filter by, e.g. if the trial is recruiting then it will be status 'RECRUITING'. This is not a required field and actually shouldn't be provided unless you actually need to filter by a different clinical trial status.",
        example=["NOT_YET_RECRUITING", "RECRUITING"],
    )


@tool(
    description="Get current data about clinical trials using clinicaltrials.gov API. Returns a list of summaries about clinical trials satisfying the filter criteria sorted in descending order by LastUpdatePostDate.",
    args_schema=GetClinicalTrialsInput,
)
def get_clinical_trials(
    condition: str,
    overall_status: list[OverallStatusOptions] | None = None,
) -> list[dict]:

    # Default overall_status
    if overall_status is None:
        overall_status = ["NOT_YET_RECRUITING", "RECRUITING"]

    fields = [
        "NCTId",
        "BriefTitle",
        "Acronym",
        "OverallStatus",
        "Condition",
        "PrimaryOutcomeMeasure",
        "PrimaryOutcomeTimeFrame",
        "LeadSponsorName",
        "CollaboratorName",
        "Sex",
        "MinimumAge",
        "MaximumAge",
        "StudyType",
        "LastUpdatePostDate",
    ]
    query_params = {
        "query.cond": condition,
        "query.locn": "florida",
        "filter.overallStatus": "|".join(overall_status),
        "fields": "|".join(fields),
        "sort": "LastUpdatePostDate",  # Sort by most recent LastUpdatePostDate
    }

    response = requests.get(
        "https://clinicaltrials.gov/api/v2/studies", params=query_params
    )  # Must use requests library because API returns 403 when using httpx

    response.raise_for_status()

    response_body = response.json()
    studies = response_body["studies"]
    return studies


class GetClinicalTrialByNCTIdInput(BaseModel):
    nct_id: str = Field(
        pattern=r"^[Nn][Cc][Tt]0*[1-9]\d{0,7}$",
        description="NCT Number of a study. Basically the ID of a clinical trial.",
    )


@tool(
    description="Get complete information about a clinical trial by its NCT Number/Id. This tool should be used if more information about the clinical trial is required beyond what is provided in the summary.",
    args_schema=GetClinicalTrialByNCTIdInput,
)
def get_clinical_trial_by_id(nct_id: str) -> dict:

    response = requests.get(
        f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
        allow_redirects=True,  # Allow redirects because the API may return 301 redirect to the study info
    )  # Must use requests library because API returns 403 when using httpx
    response.raise_for_status()

    response_body = response.json()
    return response_body


model = init_chat_model("google_genai:gemini-2.5-flash-lite", temperature=0)


class ClinicianBreastCancerAssistant(Assistant):

    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    @property
    def assistant_name(self) -> AssistantSlug:
        return "clinician-breast-cancer"

    def _build_config(self) -> dict:
        config = {
            "configurable": {
                "thread_id": str(
                    self.conversation.id
                ),  # LangGraph likes string thread_id
                "user_id": self.conversation.user_id,
                "patient_id": self.conversation.patient_id,
            },
            "checkpoint_ns": self.assistant_name,
        }
        return config

    def _get_system_prompt(self) -> str:
        prompt = """
            You are a specialized medical AI agent for doctors focused on breast cancer named Barry. You have access to comprehensive information about breast cancer and tools to gain information about patients to provide to doctor users.

            IMPORTANT INSTRUCTIONS:
            1. Always prioritize information from the provided knowledge base and that can be obtained from the tools provided to you.
            2. Feel free to use the tools to retrieve patient-specific information when needed to answer questions about breast cancer patients. If the conversation is about a specific patient, assume that the patient ID provided in the conversation context is the one to use for any patient-related queries. Otherwise, you may infer the patient ID from the user's questions.
            3. If the question is answered in the knowledge base, reference that information
            4. If the question is not fully covered in the knowledge base, use your general medical knowledge but clearly indicate this
            5. Always recommend consulting with healthcare providers for personalized medical advice
            6. Be empathetic and supportive when discussing patient concerns
            7. Focus specifically on breast cancer topics
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
        if self.conversation.patient_id:
            prompt += f"You are chatting with a doctor about breast cancer patient with ID {self.conversation.patient_id}. If the user asks about any patient details you should call the appropriate tool with this patient id. If they ask any questions related to a patient assume it is about this patient with ID {self.conversation.patient_id}, and call the appropriate tools to gain relevant information."
        return prompt

    def invoke(self, user_message: str) -> str:
        config = self._build_config()

        with PyMySQLSaver.from_conn_string(get_db_connection_string()) as saver:

            agent = create_react_agent(
                model=model,
                tools=[
                    explain_diagnosis,
                    get_patient_info,
                    get_clinical_trials,
                    get_clinical_trial_by_id,
                ],
                prompt=self._get_system_prompt(),
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

    @staticmethod
    def get_title(message: str) -> str:

        prompt = """
            You are an expert in creating concise but expressive titles.
            You will create titles for a chatbot where users can have multiple conversations.
            You will take in the user's first message and create a concise title (40 characters or less) for the conversation.
            The title should concisely describe what the conversation is about and what the user is asking.
            The casing should be that of a sentence: The first word should be capitalized but everything else (except names) should be lowercase
        """
        messages = [("system", prompt), ("human", message)]
        response = model.invoke(messages)
        return response.content
