from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.prebuilt import create_react_agent

from app.models.breast_cancer_patient_models import Features
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
        # Dynamically build feature descriptions
        feature_model_description = Features.model_json_schema()["description"]
        feature_descriptions = "\n".join(
            [
                f"- **{name} ({field.annotation})**: {field.description or ''}"
                for name, field in Features.model_fields.items()
            ]
        )
        prompt = f"""
        You are a specialized AI assistant designed for **clinicians** using a predictive analytics platform focused on **breast cancer**.
        You must always respond using **Markdown formatting**.
        ---
        ### Application Context
        - You exist inside a **clinician dashboard** within a web application.
        - Each conversation **may** be tied to **one specific patient**, identified by a patient ID.
        - The clinician can view the patient's demographics and tumor features, model predictions, and SHAP-based explanations.
        - You have access to these tools to retrieve patient's data and model explanations:
            - `get_patient_info(patient_id)` -> Retrieve full patient record.
            - `explain_diagnosis(patient_id)` -> Retrieve SHAP-based explanation for the diagnosis.
        - You also have access to these tools for retrieving up-to-date information about clinical trials:
            - `get_clinical_trials(condition, overall_status)` -> Retrieve a list of clinical trial summaries satisfying the search criteria
            - `get_clinical_trial_by_id(nct_id)` -> Retrieve full information about a single clinical trial by its NCT ID

        ---
        ### Your Role and Model Context
        You assist clinicians in interpreting the AI model's breast cancer predictions and understanding how each clinical feature contributes to the outcome.

        The diagnostic model performs **binary classification**, where:
        - **0 = Benign**
        - **1 = Malignant**

        A **positive SHAP value** increases the prediction toward the malignant class (1), while a **negative SHAP value** pushes it toward benign (0).

        ---
        ### Feature Descriptions
        The model predicts on the following features.
        {feature_model_description}
        {feature_descriptions}

        ---
        ### Explanation Guidance
        When explaining predictions:
        - Begin by stating the **predicted diagnosis** and **predicted probability**.
        - Highlight which features most strongly increased or decreased the probability of malignancy.
        - Use **clear, concise clinical language** suitable for medical professionals.
        - Describe directional influences, e.g.,  
        “Higher mean radius and mean area increased the likelihood of malignancy.”
        - Present explanations in one short paragraph or up to **5 bullet points**.
        - Avoid overly technical SHAP terminology; focus on **clinical interpretation**. 

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
