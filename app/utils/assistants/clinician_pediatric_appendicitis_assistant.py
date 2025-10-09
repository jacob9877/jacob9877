import json
from typing import Literal

from fastapi import HTTPException, status
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.models.conversation_models import AssistantSlug, Conversation
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.llm import llm
from app.utils.db import (
    db_connection_cm,
    get_db_connection_string,
    get_pediatric_appendicitis_patient_by_id,
)


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

    if patient_id != config["configurable"].get("patient_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    with db_connection_cm() as conn:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

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
        description="The integer ID (MySQL PK) of the pediatric appendicitis patient to retrieve explanation for",
        example=123,
    )
    prediction: Literal["diagnosis", "management", "severity", "length_of_stay"] = (
        Field(
            ...,
            description="The prediction to get an explanation for",
            example="diagnosis",
        )
    )


@tool(
    description="Explain a pediatric appendicitis patient's prediction using SHAP analysis based on their patient ID. Call this tool when asked for any reasoning behind the predictions/diagnoses.",
    args_schema=GetPatientExplanationInput,
)
def explain_diagnosis(
    patient_id: int,
    prediction: Literal["diagnosis", "management", "severity", "length_of_stay"],
    *,
    config: RunnableConfig,
) -> dict:

    # If the conversation is about a patient, make ture this tool call is about the same patient
    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    explanation_column = f"{prediction}_explanation"

    with db_connection_cm() as conn:
        with conn.cursor(dictionary=True) as cursor:

            operation = f"""
                SELECT pae.{explanation_column},
                    pap.user_id
                FROM pediatric_appendicitis_explanations AS pae
                JOIN pediatric_appendicitis_patients AS pap
                ON pae.patient_id = pap.id
                WHERE pae.patient_id = %s
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

    return json.loads(row[explanation_column])


class ClinicianPediatricAppendicitisAssistant(Assistant):
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    @property
    def assistant_name(self) -> AssistantSlug:
        return "clinician-pediatric-appendicitis"

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
            You are a specialized medical AI agent for doctors focused on pediatric appendicitis. You have access to comprehensive information about pediatric appendicitis and tools to gain information about patients to provide to doctor users.
            You are part of a system that uses machine learning to predict the following about a given pediatric appendicitis patient:
            1. Diagnosis: "appendicitis" or "no appendicitis"
            2. Management: "conservative" or "surgical"
            3. Severity: "complicated" or "uncomplicated"
            4. Length of Stay: a numeric prediction of the length of stay in days, along with a 80% confidence prediction interval (lower and upper bound)

            IMPORTANT INSTRUCTIONS:
            1. Always prioritize information from the provided knowledge base and that can be obtained from the tools provided to you.
            2. Feel free to use the tools to retrieve patient-specific information when needed to answer questions about pediatric appendicitis patients. If the conversation is about a specific patient, assume that the patient ID provided in the conversation context is the one to use for any patient-related queries. Otherwise, you may infer the patient ID from the user's questions.
            3. If the question is answered in the knowledge base, reference that information
            4. If the question is not fully covered in the knowledge base, use your general medical knowledge but clearly indicate this
            5. Always recommend consulting with healthcare providers for personalized medical advice
            6. Be empathetic and supportive when discussing patient concerns
            7. Focus specifically on pediatric appendicitis topics
            8. Keep responses brief. For example, one paragraph or up to 5 bullet points.

            Please provide helpful, accurate information about pediatric appendicitis while emphasizing the importance of professional medical consultation.
        """
        if self.conversation.patient_id:
            prompt += f"You are chatting with a doctor about pediatric appendicitis patient with ID {self.conversation.patient_id}. If the user asks about any patient details you should call the appropriate tool with this patient id. If they ask any questions related to a patient assume it is about this patient with ID {self.conversation.patient_id}, and call the appropriate tools to gain relevant information."
        return prompt

    def invoke(self, user_message: str) -> str:
        config = self._build_config()

        with PyMySQLSaver.from_conn_string(get_db_connection_string()) as saver:

            agent = create_react_agent(
                model=llm,
                tools=[get_patient_info, explain_diagnosis],
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
        response = llm.invoke(messages)
        return response.content
