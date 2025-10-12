from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent

from app.models.conversation_models import AssistantSlug, Conversation
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.clinician_breast_cancer_assistant.tools import (
    explain_diagnosis,
    get_patient_info,
)
from app.utils.assistants.common_tools import (
    get_clinical_trial_by_id,
    get_clinical_trials,
)
from app.utils.assistants.llm import llm
from app.utils.db import get_db_connection_string


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
                model=llm,
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
        response = llm.invoke(messages)
        return response.content
