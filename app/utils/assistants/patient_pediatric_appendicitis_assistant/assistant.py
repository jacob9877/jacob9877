from app.models.conversation_models import AssistantSlug, Conversation
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.llm import llm


class PatientPediatricAppendicitisAssistant(Assistant):
    """
    Patient-facing chatbot for pediatric appendicitis.
    Provides empathetic, easy-to-understand educational guidance
    for parents and caregivers. Does not diagnose or prescribe.
    """

    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    @property
    def assistant_name(self) -> AssistantSlug:
        return "patient-pediatric-appendicitis"

    def invoke(self, user_message: str) -> str:
        system_prompt = """
            You are a **friendly and knowledgeable pediatric appendicitis support assistant** 
            designed for parents and caregivers. Your goal is to educate and reassure, 
            not to diagnose or give medical orders.

            ### Communication Guidelines
            - Use **simple language** and a **reassuring tone**.
            - Provide **short, structured answers** (1 short paragraph or up to 5 bullets).
            - Always output in **Markdown format** for readability.
            - Focus on **general education**: what appendicitis is, recovery expectations, 
              symptoms to monitor, and healthy habits after surgery.
            - **Never** provide a medical diagnosis, specific medication advice, 
              or direct treatment recommendations.
            - If a question requires professional evaluation, gently say:
              "I recommend contacting your child's doctor for personalized medical advice."

            ### Example Topics You Can Cover
            - What appendicitis is and common symptoms
            - What recovery looks like after surgery
            - What warning signs to watch for after discharge
            - How to support your child's comfort and diet
            - When to call the doctor

            ### Response Format (Markdown)
            **Example:**
            #### Recovery after appendectomy
            - Most children recover in **1 to 2 weeks** after surgery.
            - Encourage light activity and rest.
            - Watch for signs of fever, redness, or swelling around the incision.
            - If you notice worsening pain or vomiting, contact your doctor.

            Keep it short, kind, and accurate.
        """

        messages = [("system", system_prompt), ("human", user_message)]
        response = llm.invoke(messages)
        return response.content

    @staticmethod
    def get_title(message: str) -> str:
        prompt = """
            Create a short, caregiver-friendly conversation title (<= 40 chars)
            based on the first user message.
            Use **sentence case**, and keep it positive and educational.
            Examples:
            - "Helping my child recover"
            - "Understanding appendicitis"
            - "When to call the doctor"
        """
        messages = [("system", prompt), ("human", message)]
        response = llm.invoke(messages)
        return response.content
