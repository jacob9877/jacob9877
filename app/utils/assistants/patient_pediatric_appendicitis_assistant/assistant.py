from app.models.conversation_models import AssistantSlug
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.llm import llm


class PatientPediatricAppendicitisAssistant(Assistant):

    @property
    def assistant_name(self) -> AssistantSlug:
        return "patient-pediatric-appendicitis"

    def invoke(self, user_message: str) -> str:
        system_prompt = """
            You are a patient-facing medical support assistant focused on pediatric appendicitis.
            Your audience is a parent or caregiver. Keep it simple and supportive.
            Safety and clarity guidelines:
            - Be empathetic and clear; avoid technical jargon.
            - Do not give medical directives; recommend contacting a clinician for medical decisions.
            - Provide general information about recovery, symptoms, and follow-up.
            - Keep responses concise (a short paragraph or up to 5 bullets).
            - Never provide diagnosis or treatment instructions.
        """
        messages = [("system", system_prompt), ("human", user_message)]
        response = llm.invoke(messages)
        return response.content

    @staticmethod
    def get_title(message: str) -> str:
        prompt = """
            Create a short, caregiver-friendly conversation title (<= 40 chars)
            based on the first user message. Use sentence case.
        """
        messages = [("system", prompt), ("human", message)]
        response = llm.invoke(messages)
        return response.content

