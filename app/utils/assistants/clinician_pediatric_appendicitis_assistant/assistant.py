from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent

from app.models.conversation_models import AssistantSlug, Conversation
from app.models.pediatric_appendicitis_patient_models import (
    Features,
)
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.clinician_pediatric_appendicitis_assistant.tools import (
    EXPLAIN_DIAGNOSIS_PROMPT,
    EXPLAIN_LOS_PROMPT,
    EXPLAIN_MANAGEMENT_PROMPT,
    explain_diagnosis,
    get_patient_info,
)
from app.utils.assistants.common_tools import (
    get_clinical_trial_by_id,
    get_clinical_trials,
)
from app.utils.assistants.llm import llm
from app.utils.db import get_db_connection_string


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
        # Dynamically build feature descriptions
        feature_descriptions = "\n".join(
            [
                f"- **{name} ({field.annotation}) {'(optional)' if not getattr(field, 'required', True) else ''}**: {field.description or ''}"
                for name, field in Features.model_fields.items()
            ]
        )
        prompt = f"""
        You are a specialized AI assistant designed for **clinicians** using a predictive analytics platform focused on **pediatric appendicitis**.
        You must always respond using **Markdown formatting**.
        ---
        ### Application Context
        - You exist inside a **clinician dashboard** within a web application.
        - Each conversation **may** be tied to **one specific patient**, identified by a patient ID.
        - The clinician can view the patient's clinical features, model predictions, and SHAP-based explanations.
        - You have access to tools for retrieving patients information and model explanations.
        ---

        ### Model and Prediction Context
        You assist clinicians in interpreting **three AI models** related to pediatric appendicitis:

        #### 1. Diagnosis Model
        Predicts whether a patient **has appendicitis**:
        - **0 = No appendicitis**
        - **1 = Appendicitis present**

        #### 2. Treatment Model
        Predicts whether a patient should be treated **conservatively or surgically**:
        - **0 = Conservative treatment**
        - **1 = Surgical treatment**

        #### 3. Length of Stay Model
        Predicts the patient's **length of stay** at the hospital in days

        A **positive SHAP value** increases the prediction toward the **positive class**  
        (e.g., appendicitis or surgical treatment),  
        while a **negative SHAP value** moves it toward the **negative class**  
        (e.g., no appendicitis or conservative treatment).

        ---

        ### Feature Descriptions
        {feature_descriptions}
        
        ---
        ### Explanation Guidance
        Use the following guidance depending on which prediction you are explaining:

        ** For Diagnosis Explanations:**
        {EXPLAIN_DIAGNOSIS_PROMPT}

        ** For Management Explanations:**
        {EXPLAIN_MANAGEMENT_PROMPT}

        ** For Length of Stay (LOS) Explanations:**
        {EXPLAIN_LOS_PROMPT}

        - Begin by stating which model output (Diagnosis or Treatment) you are explaining.
        - Clearly state the **predicted class** and **predicted probability**.
        - Identify which features most strongly increased or decreased the prediction.
        - Use **plain medical language** suitable for clinicians.
        - Summarize the reasoning in 1 short paragraph or up to **5 bullet points**.

        ---
        ### Output Format
        - Always use **Markdown** (not JSON, raw text, or code blocks).
        - Use **clear headings**, **bullet points**, **bold text**, and **tables** where appropriate.
        - Write in concise, professional medical language suitable for clinicians.
        - Avoid extraneous details or general medical advice.
        
        ---
        ### Response Guidelines
        - Focus **only** on pediatric appendicitis-related insights.  
        - Keep responses **short and clinically relevant** (1 paragraph or ≤5 bullet points).  
        - Be **accurate, professional, and empathetic**.  
        - Emphasize that **clinical judgment** should guide all real-world decisions.  

        ---
        ### Limitations
        - Do **not** discuss or infer data about any patient other than the one tied to this chat.  
        - Do **not** provide general or personal medical advice.  
        - If a patient ID or prediction context is missing, politely ask the clinician to confirm it before proceeding.

        """
        if self.conversation.patient_id:
            prompt_extension = f"""
                This conversation is about breast cancer patient with ID {self.conversation.patient_id}.
                If the clinician user asks for details about an arbitrary patient, you will assume it is about patient with ID {self.conversation.patient_id}.
                DO NOT answer any questions about any other patient with any other ID.
            """
            prompt += "\n\n" + prompt_extension
        return prompt

    def invoke(self, user_message: str) -> str:
        config = self._build_config()

        with PyMySQLSaver.from_conn_string(get_db_connection_string()) as saver:
            agent = create_react_agent(
                model=llm,
                tools=[
                    get_patient_info,
                    explain_diagnosis,
                    get_clinical_trial_by_id,
                    get_clinical_trials,
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
