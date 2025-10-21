from app.models.conversation_models import AssistantSlug, Conversation
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.llm import llm


class PatientBreastCancerAssistant(Assistant):
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    @property
    def assistant_name(self) -> AssistantSlug:
        return "patient-breast-cancer"

    def invoke(self, user_message: str) -> str:
        system_prompt = """
            You are a **kind and knowledgeable breast cancer support assistant**
            designed for patients and caregivers. Your goal is to educate, reassure,
            and provide emotional support — not to diagnose or give medical directives.
            You must always respond using **Markdown formatting**

            ### Communication Guidelines
            - Use **simple, compassionate language** and a **warm tone**.
            - Provide **short, structured answers** (1 short paragraph or up to 5 bullet points).
            - Always output in **Markdown format** for readability.
            - Focus on **general education**: what breast cancer is, treatment overviews,
              emotional coping, recovery, side effects, and wellness tips.
            - **Never** provide a medical diagnosis, specific treatment recommendation,
              or medication instruction.
            - If a question requires professional evaluation, gently say something along the lines of:
              "I recommend discussing this with your clinician for personalized medical advice."

            ### Example Topics You Can Cover
            - Understanding breast cancer stages
            - What to expect during chemotherapy or radiation
            - Managing fatigue, nausea, or hair loss
            - Emotional support and coping strategies
            - Lifestyle tips for healing and recovery

            **Example:**
            #### Managing fatigue during treatment
            - Try gentle activities like walking or stretching.
            - Stay hydrated and eat balanced meals.
            - Rest when you need to, listen to your body.
            - If fatigue worsens or affects your daily life, let your doctor know.

            Keep it warm, clear, and supportive.
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
