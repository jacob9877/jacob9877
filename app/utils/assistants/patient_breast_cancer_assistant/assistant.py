from app.models.conversation_models import AssistantSlug
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.llm import llm


class PatientBreastCancerAssistant(Assistant):

    @property
    def assistant_name(self) -> AssistantSlug:
        return "patient-breast-cancer"

    def invoke(self, user_message: str) -> str:
        system_prompt = """
            You are a patient-facing medical support assistant focused on breast cancer.
            Your audience is a patient or caregiver, not a clinician.
            Safety and clarity guidelines:
            - Be empathetic, supportive, and easy to understand.
            - Avoid giving medical directives; suggest consulting their clinician for decisions.
            - When discussing treatments, side effects, recovery, or lifestyle, provide general information only.
            - Keep responses concise (a short paragraph or up to 5 bullets).
            - Never provide diagnosis or treatment instructions.
        """
        messages = [("system", system_prompt), ("human", user_message)]
        response = llm.invoke(messages)
        return response.content

    @staticmethod
    def get_title(message: str) -> str:
        prompt = """
            Create a short, patient-friendly conversation title (<= 40 chars)
            based on the first user message. Use sentence case.
        """
        messages = [("system", prompt), ("human", message)]
        response = llm.invoke(messages)
        return response.content

