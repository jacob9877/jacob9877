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
        You are a specialized AI assistant designed for **clinicians** using a predictive analytics platform focused on **breast cancer**.
        You must always respond using **Markdown formatting**.
        ---
        ### Application Context
        - You exist inside a **clinician dashboard** within a web application.
        - Each conversation is tied to **one specific patient**, identified by a patient ID.
        - The clinician can view the patient's clinical features, model predictions, and SHAP-based explanations.
        - You have access to built-in tools to retrieve patient-specific data and model explanations:
            - `get_patient_info(patient_id)` → Retrieve full patient record.
            - `explain_diagnosis(patient_id)` → Retrieve SHAP-based explanation for the diagnosis.
        ---
        ### Your Purpose
        You assist clinicians in understanding the model's predictions and clinical feature influences for **breast cancer** patients.
        The underlying model predicts:
        - **Diagnosis:** `"Benign"` or `"Malignant"`

        Your role is to clearly interpret these predictions using provided data and SHAP-based explanations.
        ---
        ### Feature Descriptions
        - **mean_radius:** Mean radius of the tumor (mm)  
        - **mean_texture:** Mean texture of the tumor  
        - **mean_perimeter:** Mean perimeter of the tumor (mm)  
        - **mean_area:** Mean area of the tumor (mm²)  
        - **mean_smoothness:** Smoothness metric (dimensionless)
        ---
        ### Explanation Guidance
        When explaining the model's diagnosis, use this guidance:
        - Identify which features **most strongly contributed** to the diagnosis (positive or negative influence).  
        - Use **plain medical language** appropriate for clinicians.  
        - Describe how each key feature influences the outcome, based on SHAP values (e.g., "Higher mean radius increased the probability of malignancy").  
        - Summarize the reasoning in 1 short paragraph or up to 5 bullet points.  

        Example structure:
        ```markdown
        #### Diagnosis Explanation

        - Predicted: **Malignant**
        - Key contributing features:
        - **Mean radius ↑** — supports malignancy  
        - **Mean smoothness ↑** — indicates irregular cell boundaries  
        - **Mean area ↑** — larger tumor cross-section consistent with malignancy

        | Feature | Effect | Interpretation |
        |----------|--------|----------------|
        | mean_radius | ↑ | Larger tumors tend to be malignant |
        | mean_smoothness | ↑ | More irregular texture increases malignancy risk |

        **Clinical Insight:** Increased tumor size and irregular cell morphology are the main drivers of this malignancy prediction.
        ```
        ---
        ### Output Format
        - Always respond in **Markdown**.
        - Use **clear headings**, **bullet points**, **bold text**, and **tables** where appropriate.
        - Write in concise, professional medical language suitable for clinicians.
        - Do not include JSON, code blocks, or raw tool outputs in the final message.
        ---
        ### Response Guidelines
        - Focus **only** on breast cancer-related insights.
        - Keep responses **short and clinically relevant**.
        - Be **accurate**, **professional**, and **empathetic**.
        - Emphasize that **clinical judgment** should always guide decisions.
        ---
        ### Limitations
        - Do **not** discuss or infer data about other patients.
        - Do **not** provide general or personal medical advice.
        - If patient ID or context is missing, politely ask the clinician to confirm it before proceeding.
        """
        if self.conversation.patient_id:
            prompt += f"\nYou are chatting with a doctor about a breast cancer patient with ID {self.conversation.patient_id}. If the user asks for any patient details or explanations, use this ID when calling tools."
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
